from django.db import migrations


def create_information_pages(apps, schema_editor):
    Page = apps.get_model('core', 'Page')
    for slug, title in [
        ('about', 'О нас'),
        ('mission', 'Миссия и видение'),
        ('board', 'Совет правления'),
        ('career', 'Карьера'),
        ('contacts', 'Контакты'),
    ]:
        Page.objects.using(schema_editor.connection.alias).get_or_create(
            slug=slug, defaults={'title': title, 'body': ''},
        )


class Migration(migrations.Migration):
    dependencies = [('core', '0001_initial')]

    operations = [
        migrations.RunPython(create_information_pages, migrations.RunPython.noop),
    ]
