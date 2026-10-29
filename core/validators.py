import re
import warnings
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree

from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError


MAX_IMAGE_PIXELS = 20_000_000
RASTER_FORMATS = {'.png': 'PNG', '.jpg': 'JPEG', '.jpeg': 'JPEG', '.webp': 'WEBP', '.ico': 'ICO'}


def validate_logo(value):
    validate_image(value, limit_mb=2)


def validate_photo(value):
    validate_image(value, limit_mb=8)


def validate_favicon(value):
    if Path(value.name).suffix.lower() == '.ico':
        if not 0 < value.size <= 2 * 1024 * 1024:
            raise ValidationError('Выберите корректный ICO размером до 2 МБ.')
        validate_raster(read_image(value, 2), '.ico')
    else:
        validate_logo(value)


def read_image(value, limit_mb):
    limit = limit_mb * 1024 * 1024
    if not 0 < value.size <= limit:
        raise ValidationError(f'Размер изображения не должен превышать {limit_mb} МБ.')
    position = value.tell()
    try:
        value.seek(0)
        content = value.read(limit + 1)
    finally:
        value.seek(position)
    if len(content) != value.size or len(content) > limit:
        raise ValidationError('Не удалось прочитать изображение.')
    return content


def validate_raster(content, extension):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as image:
                if image.format != RASTER_FORMATS[extension]:
                    raise ValueError('Unexpected image format')
                width, height = image.size
                if not 0 < width * height <= MAX_IMAGE_PIXELS:
                    raise ValueError('Oversized image dimensions')
                if getattr(image, 'n_frames', 1) != 1:
                    raise ValueError('Animated images are not supported')
                image.verify()
            # verify() checks the container; load() also validates the actual pixels.
            with Image.open(BytesIO(content)) as image:
                image.load()
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, EOFError,
            Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise ValidationError('Выберите корректное статичное изображение размером до 20 миллионов пикселей.') from error


def validate_image(value, limit_mb):
    content = read_image(value, limit_mb)

    extension = Path(value.name).suffix.lower()
    if extension in RASTER_FORMATS and extension != '.ico':
        validate_raster(content, extension)
        return
    if extension != '.svg':
        raise ValidationError('Используйте SVG, PNG, JPG или WebP.')

    # Restrict the stored source to UTF-8 too: a byte regex cannot inspect UTF-16,
    # and ElementTree discards XML processing instructions after parsing.
    try:
        source = content.decode('utf-8-sig')
    except UnicodeDecodeError as error:
        raise ValidationError('Сохраните SVG в кодировке UTF-8.') from error
    declared_encoding = re.match(r'''\s*<\?xml\b[^>]*\bencoding\s*=\s*['"]([^'"]+)['"]''', source, re.IGNORECASE)
    if '\x00' in source or (declared_encoding and declared_encoding[1].lower() not in {'utf-8', 'utf8'}):
        raise ValidationError('Сохраните SVG в кодировке UTF-8.')

    # Standard SVG exports may declare a public SVG DTD. ElementTree does not
    # fetch external DTDs; internal subsets and entity declarations are rejected.
    if re.search(r'<!ENTITY|<!DOCTYPE[^>]*\[|<\?xml-stylesheet\b', source, re.IGNORECASE):
        raise ValidationError('SVG не должен содержать определения сущностей или внешние стили XML.')
    try:
        root = ElementTree.fromstring(source)
    except ElementTree.ParseError as error:
        raise ValidationError('Не удалось прочитать SVG-файл.') from error

    if root.tag not in {'svg', '{http://www.w3.org/2000/svg}svg'}:
        raise ValidationError('Выберите корректный SVG-логотип.')

    for element in root.iter():
        tag = element.tag.rsplit('}', 1)[-1].lower()
        if tag in {'script', 'foreignobject', 'iframe', 'object', 'embed', 'animate', 'animatemotion', 'animatetransform', 'set', 'discard'}:
            raise ValidationError('SVG должен быть статичным и не содержать скрипты или HTML.')
        styles = [element.text or ''] if tag == 'style' else []
        for key, value in element.attrib.items():
            attribute = key.rsplit('}', 1)[-1].lower()
            if attribute.startswith('on'):
                raise ValidationError('SVG не должен содержать обработчики событий.')
            if attribute == 'href' and not (
                value.startswith('#') or re.match(r'^data:image/(?:png|jpeg|webp);base64,', value)
            ):
                raise ValidationError('SVG не должен загружать внешние ресурсы.')
            if attribute == 'style' or 'url(' in value.lower():
                styles.append(value)
        for style in styles:
            references = re.findall(r'url\(([^)]*)\)', style, re.IGNORECASE)
            if '\\' in style or '@import' in style.lower() or any(not ref.strip(' \t\r\n\'"').startswith('#') for ref in references):
                raise ValidationError('SVG не должен загружать внешние стили или изображения.')
