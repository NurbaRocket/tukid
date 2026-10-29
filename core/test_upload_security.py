from io import BytesIO
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from PIL import Image
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from .career_files import MAX_PDF_STREAM_SIZE, validate_resume
from .validators import validate_favicon, validate_logo


def raster_bytes(format_name):
    output = BytesIO()
    Image.new('RGB', (32, 32), 'white').save(output, format=format_name)
    return output.getvalue()


def pdf_bytes(configure=None, pages=1):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=595, height=842)
    if configure:
        configure(writer)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


class ImageUploadSecurityTests(SimpleTestCase):
    def test_real_raster_images_and_favicon_are_accepted_without_moving_cursor(self):
        for extension, format_name in [('png', 'PNG'), ('jpg', 'JPEG'), ('webp', 'WEBP'), ('ico', 'ICO')]:
            with self.subTest(extension=extension):
                upload = SimpleUploadedFile(f'image.{extension}', raster_bytes(format_name))
                upload.seek(2)
                (validate_favicon if extension == 'ico' else validate_logo)(upload)
                self.assertEqual(upload.tell(), 2)

    def test_fake_truncated_and_mislabeled_images_are_rejected(self):
        for filename, content in [
            ('fake.png', b'\x89PNG\r\n\x1a\n'),
            ('fake.jpg', b'\xff\xd8\xff'),
            ('fake.webp', b'RIFF1234WEBP'),
            ('fake.ico', b'\x00\x00\x01\x00'),
            ('truncated.png', raster_bytes('PNG')[:40]),
            ('wrong.png', raster_bytes('JPEG')),
        ]:
            with self.subTest(filename=filename), self.assertRaises(ValidationError):
                (validate_favicon if filename.endswith('.ico') else validate_logo)(
                    SimpleUploadedFile(filename, content))

    def test_pixel_limit_is_checked_before_decoding(self):
        with patch('core.validators.MAX_IMAGE_PIXELS', 100):
            with self.assertRaises(ValidationError):
                validate_logo(SimpleUploadedFile('large.png', raster_bytes('PNG')))

    def test_utf16_utf32_and_mismatched_svg_encodings_are_rejected(self):
        for encoding in ['utf-16', 'utf-16-le', 'utf-16-be', 'utf-32']:
            content = (
                f'<?xml version="1.0" encoding="{encoding}"?>'
                '<?xml-stylesheet href="https://example.invalid/style.css"?>'
                '<svg xmlns="http://www.w3.org/2000/svg"/>'
            ).encode(encoding)
            with self.subTest(encoding=encoding), self.assertRaises(ValidationError):
                validate_logo(SimpleUploadedFile('logo.svg', content))
        with self.assertRaises(ValidationError):
            validate_logo(SimpleUploadedFile('logo.svg',
                b'<?xml version="1.0" encoding="UTF-16"?><svg/>'))

    def test_utf8_bom_and_non_ascii_svg_text_remain_supported(self):
        content = '\ufeff<?xml version="1.0" encoding="UTF-8"?><svg><text>Кыргызча Türkçe</text></svg>'
        validate_logo(SimpleUploadedFile('logo.svg', content.encode('utf-8')))


class PDFUploadSecurityTests(SimpleTestCase):
    def validate(self, content):
        upload = SimpleUploadedFile('resume.pdf', content)
        upload.seek(2)
        validate_resume(upload)
        self.assertEqual(upload.tell(), 2)
        upload.seek(0)
        self.assertEqual(upload.read(), content)

    def test_plain_pdf_and_regular_hyperlink_are_accepted_without_rewriting(self):
        self.validate(pdf_bytes())
        self.validate(pdf_bytes(lambda writer: writer.add_uri(
            0, 'https://example.com/portfolio', [0, 0, 100, 100])))

    def test_fake_pdf_and_broken_structure_are_rejected(self):
        for content in [
            b'%PDF-1.7\nThis is not a PDF\n%%EOF',
            pdf_bytes().replace(b'startxref', b'brokenref'),
            pdf_bytes(pages=0),
        ]:
            with self.subTest(size=len(content)), self.assertRaises(ValidationError):
                self.validate(content)

    def test_active_content_attachments_and_encryption_are_rejected(self):
        configurations = [
            lambda writer: writer.add_js('app.alert("unsafe")'),
            lambda writer: writer.add_attachment('payload.txt', b'attachment'),
            lambda writer: writer.add_uri(0, 'javascript:alert(1)', [0, 0, 100, 100]),
            lambda writer: writer.encrypt('password'),
        ]
        for configure in configurations:
            with self.subTest(configure=configure), self.assertRaises(ValidationError):
                self.validate(pdf_bytes(configure))

    def test_excessive_page_count_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.validate(pdf_bytes(pages=51))

    def test_indirect_action_name_cannot_bypass_active_content_check(self):
        def indirect_launch(writer):
            action = DictionaryObject({
                NameObject('/S'): writer._add_object(NameObject('/Launch')),
                NameObject('/F'): NameObject('/payload.exe'),
            })
            writer.pages[0][NameObject('/A')] = writer._add_object(action)

        with self.assertRaises(ValidationError):
            self.validate(pdf_bytes(indirect_launch))

    def test_compressed_stream_expansion_is_limited(self):
        def expanded_stream(writer):
            stream = DecodedStreamObject()
            stream.set_data(b' ' * (MAX_PDF_STREAM_SIZE + 1))
            writer.pages[0][NameObject('/Contents')] = writer._add_object(stream.flate_encode())

        content = pdf_bytes(expanded_stream)
        self.assertLess(len(content), 20_000)
        with self.assertRaises(ValidationError):
            self.validate(content)
