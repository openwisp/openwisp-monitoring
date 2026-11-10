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


def is_monitoring_blocked(obj):
    """
    Whether monitoring operations must be skipped for a related object.

    Duck-typed so it works across generic relations: a deactivated
    device or a device belonging to a disabled organization blocks
    monitoring, everything else (None, non-device content objects) does
    not.
    """
    if obj is None:
        return False
    if hasattr(obj, "is_deactivated") and obj.is_deactivated():
        return True
    organization = getattr(obj, "organization", None)
    return organization is not None and not organization.is_active
