import logging
from functools import wraps
from time import sleep

from django.apps import apps
from django.db import transaction
from swapper import is_swapped, split

from .settings import MONITORING_TIMESERIES_RETRY_OPTIONS

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
        max_retries = MONITORING_TIMESERIES_RETRY_OPTIONS.get('max_retries')
        delay = MONITORING_TIMESERIES_RETRY_OPTIONS.get('delay')
        for attempt_no in range(1, max_retries + 1):
            try:
                return method(*args, **kwargs)
            except Exception as err:
                logger.info(
                    f'Error while executing method "{method.__name__}":\n{err}\n'
                    f'Attempt {attempt_no} out of {max_retries}.\n'
                )
                if attempt_no > 3:
                    sleep(delay)
                if attempt_no == max_retries:
                    raise err

    return wrapper
