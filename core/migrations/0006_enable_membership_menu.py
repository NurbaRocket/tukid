from django.db import migrations


def enable_membership(apps, schema_editor):
    MenuItem = apps.get_model('core', 'MenuItem')
    db = schema_editor.connection.alias
    items = MenuItem.objects.using(db)
    target = items.filter(title__iexact='Стать членом ассоциации', parent__isnull=False).first()
    if target is None:
        parent = items.filter(parent__isnull=True, route='members').first()
        if parent is None:
            return
        target = MenuItem(parent=parent, title='Стать членом ассоциации', sort_order=10)
    target.route = 'membership'
    target.page_id = None
    target.external_url = ''
    target.is_enabled = True
    target.save(using=db)


def disable_membership(apps, schema_editor):
    apps.get_model('core', 'MenuItem').objects.using(schema_editor.connection.alias).filter(
        route='membership'
    ).update(route='', is_enabled=False)


class Migration(migrations.Migration):
    dependencies = [('core', '0005_alter_homesection_link_route_and_more')]
    operations = [migrations.RunPython(enable_membership, disable_membership)]
