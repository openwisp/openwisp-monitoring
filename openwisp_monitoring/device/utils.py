from django.apps import apps
from swapper import is_swapped, split

from ..db import timeseries_db
from . import settings as app_settings

SHORT_RP = 'short'


def get_device_cache_key(device, context='react-to-updates'):
    return f'device-{device.pk}-{context}'


def manage_short_retention_policy():
    """
    creates or updates the "short" retention policy
    """
    duration = app_settings.SHORT_RETENTION_POLICY
    timeseries_db.create_or_alter_retention_policy(SHORT_RP, duration)


def load_model_patched(app_label, model, require_ready=True):
    """
    TODO: remove if https://github.com/wq/django-swappable-models/pull/23 gets merged
    """
    swapped = is_swapped(app_label, model)
    if swapped:
        app_label, model = split(swapped)
    return apps.get_model(app_label, model, require_ready=require_ready)
