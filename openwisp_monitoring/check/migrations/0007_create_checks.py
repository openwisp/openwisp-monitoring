import swapper
from django.db import migrations

from openwisp_monitoring.check.settings import AUTO_CONFIG_CHECK, AUTO_PING
from openwisp_monitoring.check.tasks import auto_create_config_check, auto_create_ping


def create_ping_checks(apps, schema_editor):
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


def create_config_applied_checks(apps, schema_editor):
    if not AUTO_CONFIG_CHECK:
        return
    ContentType = apps.get_model('contenttypes', 'ContentType')
    Check = apps.get_model('check', 'Check')
    Device = apps.get_model('config', 'Device')
    for device in Device.objects.all():
        auto_create_config_check(
            model=Device.__name__.lower(),
            app_label=Device._meta.app_label,
            object_id=str(device.pk),
            check_model=Check,
            content_type_model=ContentType,
        )


def remove_config_applied_checks(apps, schema_editor):
    Check = apps.get_model('check', 'Check')
    Metric = apps.get_model('monitoring', 'Metric')
    Check.objects.filter(
        check='openwisp_monitoring.check.classes.ConfigApplied'
    ).delete()
    Metric.objects.filter(configuration='config_applied').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('check', '0006_rename_check_check_check_type'),
        swapper.dependency('monitoring', 'Metric'),
    ]

    operations = [
        migrations.RunPython(
            create_ping_checks, reverse_code=migrations.RunPython.noop
        ),
        migrations.RunPython(
            create_config_applied_checks, reverse_code=remove_config_applied_checks
        ),
    ]
