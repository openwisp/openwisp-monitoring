import logging
from functools import wraps
from time import sleep

from django.db import transaction

from .settings import MONITORING_TIMESERIES_RETRY_OPTIONS

logger = logging.getLogger(__name__)


def transaction_on_commit(func):
    with transaction.atomic():
        transaction.on_commit(func)


def retry(method):
    @wraps(method)
    def wrapper(*args, **kwargs):
        max_retries = MONITORING_TIMESERIES_RETRY_OPTIONS.get("max_retries")
        delay = MONITORING_TIMESERIES_RETRY_OPTIONS.get("delay")
        for attempt_no in range(1, max_retries + 1):
            try:
                return method(*args, **kwargs)
            except Exception as err:
                logger.info(
                    f'Error while executing method "{method.__name__}":\n{err}\n'
                    f"Attempt {attempt_no} out of {max_retries}.\n"
                )
                if attempt_no > 3:
                    sleep(delay)
                if attempt_no == max_retries:
                    raise err

    return wrapper


def is_write_blocked(content_type, object_id):
    """Return whether a generic relation targets a blocked object."""
    if content_type is None or not object_id:
        return False
    model = content_type.model_class()
    if model is None:
        return False
    field_names = {field.name for field in model._meta.get_fields()}
    if "_is_deactivated" not in field_names and "organization" not in field_names:
        return False
    queryset = model._default_manager.filter(pk=object_id)
    if "_is_deactivated" in field_names:
        queryset = queryset.filter(_is_deactivated=False)
    if "organization" in field_names:
        queryset = queryset.filter(organization__is_active=True)
    return not queryset.exists()
