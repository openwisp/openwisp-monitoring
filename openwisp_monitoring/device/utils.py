from django.conf import settings
from swapper import load_model

from ..db import timeseries_db
from . import settings as app_settings
from .signals import device_status_unknown

SHORT_RP = 'short'
DEFAULT_RP = 'autogen'

Device = load_model('config', 'Device')
DeviceMonitoring = load_model('device_monitoring', 'DeviceMonitoring')


def handle_critical_check_change(check):
    critical_metrics = settings.OPENWISP_MONITORING_CRITICAL_DEVICE_METRICS
    if check.object_id and check.metric.name in critical_metrics:
        device = Device.objects.get(pk=check.object_id)
        device.monitoring.update_status('unknown')
        device_status_unknown.send(sender=DeviceMonitoring, instance=device.monitoring)


def get_device_cache_key(device, context='react-to-updates'):
    return f'device-{device.pk}-{context}'


def manage_short_retention_policy():
    """
    creates or updates the "short" retention policy
    """
    duration = app_settings.SHORT_RETENTION_POLICY
    timeseries_db.create_or_alter_retention_policy(SHORT_RP, duration)


def manage_default_retention_policy():
    """
    creates or updates the "default" retention policy
    """
    duration = app_settings.DEFAULT_RETENTION_POLICY
    timeseries_db.create_or_alter_retention_policy(DEFAULT_RP, duration)
