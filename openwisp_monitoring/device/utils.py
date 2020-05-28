from ..db import TimeseriesDB
from . import settings as app_settings

SHORT_RP = 'short'


def get_device_recovery_cache_key(device):
    return f'device-{device.pk}-react-to-updates'


def manage_short_retention_policy():
    """
    creates or updates the "short" retention policy
    """
    db = TimeseriesDB().get_db()
    duration = app_settings.SHORT_RETENTION_POLICY
    retention_policies = db.get_list_retention_policies()
    exists = False
    duration_changed = False
    for policy in retention_policies:
        if policy['name'] == SHORT_RP:
            exists = True
            duration_changed = policy['duration']
            break
    if not exists:
        db.create_retention_policy(name=SHORT_RP, duration=duration, replication=1)
    elif exists and duration_changed:
        db.alter_retention_policy(name=SHORT_RP, duration=duration)
