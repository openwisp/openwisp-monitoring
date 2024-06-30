from ..db import timeseries_db
from . import settings as app_settings

SHORT_RP = 'short'
DEFAULT_RP = 'autogen'


def get_device_cache_key(device, context='react-to-updates'):
    return f'device-{device.pk}-{context}'


def manage_short_retention_policy():
    """
    creates or updates the "short" retention policy
    """
    duration = app_settings.SHORT_RETENTION_POLICY
    _manage_retention_policy(SHORT_RP, duration)


def manage_default_retention_policy():
    """
    creates or updates the "default" retention policy
    """
    duration = app_settings.DEFAULT_RETENTION_POLICY
    _manage_retention_policy(DEFAULT_RP, duration)

def _manage_retention_policy(name, duration):
    # For InfluxDB 2.x, we're not managing retention policies directly
    # Instead, we ensure the bucket exists
    timeseries_db.create_bucket(timeseries_db.bucket)
