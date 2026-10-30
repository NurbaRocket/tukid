from decimal import Decimal

from django.db import migrations


LOCATION_URL = 'https://2gis.kg/bishkek/geo/15763234351102446/74.584407%2C42.874668?m=74.584659%2C42.874736%2F19.75%2Fp%2F11.04%2Fr%2F2.81'


def set_contact_location(apps, schema_editor):
    SiteSettings = apps.get_model('core', 'SiteSettings')
    # Populate the previously empty setting; keep any explicit editor override.
    SiteSettings.objects.using(schema_editor.connection.alias).filter(pk=1, maps_url='').update(
        maps_url=LOCATION_URL, map_latitude=Decimal('42.874668'),
        map_longitude=Decimal('74.584407'), map_zoom=17,
    )


class Migration(migrations.Migration):
    dependencies = [('core', '0020_contact_messages_and_map')]
    operations = [migrations.RunPython(set_contact_location, migrations.RunPython.noop)]
