from django.conf import settings
from django.db import migrations
from swapper import load_model

Check = load_model('check', 'Check')
Device = load_model('config', 'Device')
DeviceMonitoring = load_model('device_monitoring', 'DeviceMonitoring')


def update_device_status(apps, schema_editor):
    Check = load_model('check', 'Check')
    Device = load_model('config', 'Device')
    critical_metrics_keys = [
        metric['key'] for metric in settings.OPENWISP_MONITORING_CRITICAL_DEVICE_METRICS
    ]

    for check in Check.objects.filter(
        is_active=False, metric__key__in=critical_metrics_keys
    ).iterator():
        if check.object_id:
            device = Device.objects.get(pk=check.object_id)
            device.monitoring.update_status('unknown')


class Migration(migrations.Migration):
    dependencies = [
        ('device_monitoring', '0008_alter_wificlient_options'),
    ]

    operations = [
        migrations.RunPython(
            update_device_status, reverse_code=migrations.RunPython.noop
        ),
    ]
