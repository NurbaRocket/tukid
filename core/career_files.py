from django.utils.translation import gettext_lazy as _

from io import BytesIO
from pathlib import PurePosixPath
from urllib.parse import urlsplit
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile
from zlib import error as CompressionError

from django.core.exceptions import ValidationError
from pypdf import PdfReader, apply_configuration
from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject, StreamObject

MAX_RESUME_SIZE = 5 * 1024 * 1024
MAX_PDF_PAGES = 50
MAX_PDF_OBJECTS = 10_000
MAX_PDF_STREAM_SIZE = 8 * 1024 * 1024
MAX_PDF_EXPANDED_SIZE = 25 * 1024 * 1024
RESUME_CONTENT_TYPES = {
    '.pdf': 'application/pdf',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
}


def validate_resume(upload):
    suffix = PurePosixPath(upload.name.replace('\\', '/')).suffix.lower()
    if suffix not in RESUME_CONTENT_TYPES:
        raise ValidationError(_('Прикрепите резюме в формате PDF или DOCX.'))
    if not 0 < upload.size <= MAX_RESUME_SIZE:
        raise ValidationError(_('Файл резюме должен быть непустым и не больше 5 МБ.'))
    position = upload.tell()
    try:
        upload.seek(0)
        content = upload.read(MAX_RESUME_SIZE + 1)
    finally:
        upload.seek(position)
    if len(content) != upload.size or len(content) > MAX_RESUME_SIZE:
        raise ValidationError(_('Не удалось прочитать файл резюме.'))
    if suffix == '.pdf':
        try:
            validate_pdf(content)
        except Exception as error:
            # The parser handles untrusted bytes; malformed inputs may also
            # raise Python decoding/structure errors beyond PdfReadError.
            raise ValidationError(_('Не удалось прочитать PDF. Сохраните резюме в PDF ещё раз.')) from error
        return
    try:
        validate_docx(content)
    except (BadZipFile, LookupError, ValueError, RuntimeError, NotImplementedError, OSError,
            EOFError, ElementTree.ParseError, CompressionError) as error:
        raise ValidationError(_('Не удалось прочитать DOCX. Используйте обычный документ Word без макросов и вложений.')) from error


def validate_pdf(content):
    if not content.startswith(b'%PDF-') or b'%%EOF' not in content[-2048:]:
        raise ValueError('Invalid PDF signature')
    # Context-local limits leave other PDF operations and concurrent requests alone.
    with apply_configuration(
        maximum_declared_stream_length=MAX_RESUME_SIZE,
        array_based_stream_maximum_output_length=MAX_PDF_STREAM_SIZE,
        zlib_maximum_output_length=MAX_PDF_STREAM_SIZE,
        lzw_maximum_output_length=MAX_PDF_STREAM_SIZE,
        run_length_maximum_output_length=MAX_PDF_STREAM_SIZE,
        brotli_maximum_output_length=MAX_PDF_STREAM_SIZE,
        jbig2_maximum_output_length=MAX_PDF_STREAM_SIZE,
        image_maximum_buffer_size=MAX_PDF_STREAM_SIZE,
        stream_decoding_work_maximum_length=MAX_PDF_EXPANDED_SIZE,
        dictionary_maximum_element_count=MAX_PDF_OBJECTS,
        array_maximum_element_count=MAX_PDF_OBJECTS,
        page_tree_maximum_entries=MAX_PDF_OBJECTS,
        page_tree_maximum_depth=30,
        jbig2dec_binary=None,
    ):
        with PdfReader(BytesIO(content), strict=True, xref_stream_maximum_entries=MAX_PDF_OBJECTS) as reader:
            if reader.is_encrypted:
                raise ValueError('Encrypted resumes are not supported')
            if not 0 < len(reader.pages) <= MAX_PDF_PAGES:
                raise ValueError('Too many PDF pages or empty document')
            if sum(len(entries) for entries in reader.xref.values()) + len(reader.xref_objStm) > MAX_PDF_OBJECTS:
                raise ValueError('Too many PDF objects')
            inspect_pdf_objects(reader.root_object)


def inspect_pdf_objects(root):
    # Walk the graph without recursion, resolving each reference once. Ordinary
    # hyperlinks are allowed; scripts, launch actions and embedded files are not.
    pending = [(root, 0)]
    visited = set()
    expanded = 0
    forbidden_keys = {'/AA', '/OpenAction', '/JS', '/JavaScript', '/EmbeddedFiles',
        '/EF', '/XFA', '/RichMediaContent', '/RichMediaSettings', '/Collection'}
    forbidden_types = {'/JavaScript', '/Launch', '/SubmitForm', '/ImportData',
        '/GoToR', '/GoToE', '/Rendition', '/Movie', '/Sound', '/EmbeddedFile'}
    while pending:
        value, depth = pending.pop()
        if isinstance(value, IndirectObject):
            key = ('reference', value.idnum, value.generation)
            if key in visited:
                continue
            visited.add(key)
            value = value.get_object()
        if not isinstance(value, (DictionaryObject, ArrayObject)):
            continue
        key = ('object', id(value))
        if key in visited:
            continue
        visited.add(key)
        if depth > 50 or len(visited) > MAX_PDF_OBJECTS or len(pending) > MAX_PDF_OBJECTS:
            raise ValueError('PDF object graph exceeds limits')
        if isinstance(value, DictionaryObject):
            # __getitem__ resolves indirect PDF values; dict.get() would leave
            # action names wrapped in references and miss the same action.
            action = value['/S'] if '/S' in value else None
            object_type = value['/Type'] if '/Type' in value else None
            subtype = value['/Subtype'] if '/Subtype' in value else None
            if (forbidden_keys.intersection(value) or action in forbidden_types or object_type in forbidden_types
                    or subtype in {'/RichMedia', '/Movie', '/Sound', '/Screen', '/3D', '/FileAttachment'}):
                raise ValueError('Active PDF content is not supported')
            if action == '/URI':
                uri = value['/URI'] if '/URI' in value else None
                if not isinstance(uri, str) or urlsplit(uri).scheme.lower() not in {'http', 'https', 'mailto', 'tel'}:
                    raise ValueError('Unsafe PDF hyperlink')
            if isinstance(value, StreamObject):
                data = value.get_data()
                expanded += len(data)
                if len(data) > MAX_PDF_STREAM_SIZE or expanded > MAX_PDF_EXPANDED_SIZE:
                    raise ValueError('Expanded PDF streams exceed limits')
            pending.extend((child, depth + 1) for child in value.values())
        else:
            pending.extend((child, depth + 1) for child in value)


def xml_root(content):
    if b'\x00' in content or b'<!DOCTYPE' in content.upper() or b'<!ENTITY' in content.upper():
        raise ValueError('XML entity declarations are not allowed')
    return ElementTree.fromstring(content)


def validate_docx(content):
    with ZipFile(BytesIO(content)) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        if len(entries) > 1000 or len(names) != len(set(names)):
            raise ValueError('Too many or duplicate archive entries')
        if sum(entry.file_size for entry in entries) > 25 * 1024 * 1024:
            raise ValueError('Oversized expanded document')
        for entry in entries:
            path = PurePosixPath(entry.filename.replace('\\', '/'))
            lowered = str(path).lower()
            if path.is_absolute() or '..' in path.parts or entry.flag_bits & 1:
                raise ValueError('Invalid archive path or encryption')
            if 'vbaproject' in lowered or lowered.startswith('word/embeddings/') or lowered.endswith('vbadata.xml'):
                raise ValueError('Macros and embedded objects are not supported')
        if archive.getinfo('[Content_Types].xml').file_size > 128 * 1024 or archive.getinfo('word/document.xml').file_size > 4 * 1024 * 1024:
            raise ValueError('Oversized document XML')
        types = xml_root(archive.read('[Content_Types].xml'))
        if types.tag != '{http://schemas.openxmlformats.org/package/2006/content-types}Types':
            raise ValueError('Invalid content types')
        if not any(node.attrib.get('PartName') == '/word/document.xml' and node.attrib.get('ContentType') ==
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml' for node in types):
            raise ValueError('Not a DOCX document')
        document = xml_root(archive.read('word/document.xml'))
        if document.tag not in {
            '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}document',
            '{http://purl.oclc.org/ooxml/wordprocessingml/main}document',
        }:
            raise ValueError('Invalid Word document')
        for entry in entries:
            if not entry.filename.endswith('.rels'):
                continue
            if entry.file_size > 128 * 1024:
                raise ValueError('Oversized relationships')
            for relation in xml_root(archive.read(entry)):
                if relation.attrib.get('TargetMode') == 'External' and not relation.attrib.get('Type', '').endswith('/hyperlink'):
                    raise ValueError('External document resources are not supported')
