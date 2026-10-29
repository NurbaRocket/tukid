import re

from django.db import migrations


# Frozen copy conversion for site-owned texts. Applications, PDF bytes and
# editorial records about other organizations are deliberately outside this set.
PUBLIC_COPY = {
    'SiteSettings': ['organization_name', 'site_description', 'footer_text'],
    'HomeSection': ['eyebrow', 'title', 'description', 'link_label', 'secondary_label', 'image_alt'],
    'MenuItem': ['title'],
    'Page': ['title', 'body', 'image_alt', 'meta_description'],
    'HomeDirection': ['title', 'description'],
    'GalleryPhoto': ['title', 'image_alt'],
}
REPLACEMENTS = [
    ('наша ассоциация', 'наше общественное объединение'),
    ('эта ассоциация', 'это общественное объединение'),
    ('данная ассоциация', 'данное общественное объединение'),
    ('об ассоциации', 'об объединении'),
    ('в ассоциации', 'в объединении'),
    ('при ассоциации', 'при объединении'),
    ('ассоциацией', 'объединением'),
    ('ассоциацию', 'объединение'),
    ('ассоциация', 'общественное объединение'),
    ('ассоциации', 'объединения'),
]


def update_text(value):
    def preserve_case(match, replacement):
        original = match.group()
        if original.isupper():
            return replacement.upper()
        if original[0].isupper():
            return replacement[0].upper() + replacement[1:]
        return replacement

    for source, replacement in REPLACEMENTS:
        value = re.sub(
            r'\b' + re.escape(source) + r'\b',
            lambda match: preserve_case(match, replacement),
            value, flags=re.IGNORECASE,
        )
    return value


def update_public_copy(apps, schema_editor):
    db = schema_editor.connection.alias
    for name, fields in PUBLIC_COPY.items():
        model = apps.get_model('core', name)
        for obj in model.objects.using(db).only('pk', *fields).iterator():
            changes = {}
            for field in fields:
                old = getattr(obj, field)
                new = update_text(old)
                if new != old:
                    changes[field] = new
            if changes:
                model.objects.using(db).filter(pk=obj.pk).update(**changes)


class Migration(migrations.Migration):
    dependencies = [('core', '0007_alter_member_options_alter_boardmember_position_and_more')]
    operations = [migrations.RunPython(update_public_copy, migrations.RunPython.noop)]
