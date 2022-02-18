import logging
from functools import wraps
from time import sleep

from django.apps import apps
from django.db import transaction
from swapper import is_swapped, split

from .settings import MONITORING_INFLUXDB_MAX_RETRIES, MONITORING_INFLUXDB_RETRY_DELAY

logger = logging.getLogger(__name__)


def transaction_on_commit(func):
    with transaction.atomic():
        transaction.on_commit(func)


def load_model_patched(app_label, model, require_ready=True):
    """
    TODO: remove if https://github.com/wq/django-swappable-models/pull/23 gets merged
    """
    swapped = is_swapped(app_label, model)
    if swapped:
        app_label, model = split(swapped)
    return apps.get_model(app_label, model, require_ready=require_ready)


def retry(method):
    @wraps(method)
    def wrapper(*args, **kwargs):
        for attempt_no in range(1, MONITORING_INFLUXDB_MAX_RETRIES + 1):
            try:
                return method(*args, **kwargs)
            except Exception as err:
                logger.info(
                    f'Error while executing method "{method.__name__}":\n{err}\n'
                    f'Attempt {attempt_no} out of {MONITORING_INFLUXDB_MAX_RETRIES}.\n'
                )
                if attempt_no > 3:
                    sleep(MONITORING_INFLUXDB_RETRY_DELAY)
                if attempt_no == MONITORING_INFLUXDB_MAX_RETRIES:
                    raise err

    return wrapper
