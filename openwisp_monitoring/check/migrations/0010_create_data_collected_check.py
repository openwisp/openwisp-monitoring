import swapper
from django.db import migrations

from openwisp_monitoring.check.settings import AUTO_DATA_COLLECTED_CHECK
from openwisp_monitoring.check.tasks import auto_create_check


def create_data_collected_check(apps, schema_editor):
    if AUTO_DATA_COLLECTED_CHECK:
        ContentType = apps.get_model('contenttypes', 'ContentType')
        Check = apps.get_model('check', 'Check')
        Device = apps.get_model('config', 'Device')
        for device in Device.objects.iterator():
            auto_create_check(
                model=Device.__name__.lower(),
                app_label=Device._meta.app_label,
                object_id=str(device.pk),
                check_type='openwisp_monitoring.check.classes.DataCollected',
                check_name='Monitoring Data Collected',
                check_model=Check,
                content_type_model=ContentType,
            )


def remove_data_collected_checks(apps, schema_editor):
    Check = apps.get_model('check', 'Check')
    Metric = apps.get_model('monitoring', 'Metric')
    Check.objects.filter(
        check_type='openwisp_monitoring.check.classes.DataCollected'
    ).delete()
    Metric.objects.filter(configuration='data_collected').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('check', '0009_add_check_inline_permissions'),
        swapper.dependency('monitoring', 'Metric'),
    ]

    operations = [
        migrations.RunPython(
            create_data_collected_check, reverse_code=remove_data_collected_checks
        )
    ]
