from ..db import timeseries_db
from . import settings as app_settings

SHORT_RP = 'short'


def get_device_recovery_cache_key(device):
    return f'device-{device.pk}-react-to-updates'


def manage_short_retention_policy():
    """
    creates or updates the "short" retention policy
    """
    duration = app_settings.SHORT_RETENTION_POLICY
    timeseries_db.create_or_alter_retention_policy(SHORT_RP, duration)
