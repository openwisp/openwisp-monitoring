from django.db import migrations
from swapper import load_model


def update_critical_device_metric_status(apps, schema_editor):
    Check = apps.get_model('check', 'Check')
    # We need to load the real concrete model here, because we
    # will be calling one of its class methods below
    DeviceMonitoring = load_model('device_monitoring', 'DeviceMonitoring')
    critical_metrics_keys = DeviceMonitoring._get_critical_metric_keys()

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
