from django.db import migrations

from openwisp_monitoring.check.settings import AUTO_PING
from openwisp_monitoring.check.tasks import auto_create_ping


def create_device_ping(apps, schema_editor):
    if AUTO_PING:
        ContentType = apps.get_model('contenttypes', 'ContentType')
        Check = apps.get_model('check', 'Check')
        Device = apps.get_model('config', 'Device')
        for device in Device.objects.all():
            auto_create_ping(
                model=Device.__name__.lower(),
                app_label=Device._meta.app_label,
                object_id=str(device.pk),
                check_model=Check,
                content_type_model=ContentType,
            )


class Migration(migrations.Migration):

    dependencies = [
        ('check', '0002_check_unique_together'),
    ]

    operations = [
        migrations.RunPython(create_device_ping, reverse_code=migrations.RunPython.noop)
    ]
