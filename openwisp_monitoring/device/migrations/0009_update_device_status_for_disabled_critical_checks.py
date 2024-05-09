from django.db import migrations

from openwisp_monitoring.device.settings import get_critical_device_metrics


def update_critical_device_metric_status(apps, schema_editor):
    Check = apps.get_model('check', 'Check')
    DeviceMonitoring = apps.get_model('device_monitoring', 'DeviceMonitoring')
    critical_metrics_keys = [metric['key'] for metric in get_critical_device_metrics()]

    for check in Check.objects.filter(
        is_active=False, check_type__in=critical_metrics_keys
    ).iterator():
        DeviceMonitoring.handle_critical_metric(check)


class Migration(migrations.Migration):
    dependencies = [
        ('device_monitoring', '0008_alter_wificlient_options'),
    ]

    operations = [
        migrations.RunPython(
            update_critical_device_metric_status, reverse_code=migrations.RunPython.noop
        ),
    ]
