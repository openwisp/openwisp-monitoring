import logging
from functools import wraps
from time import sleep
from django.contrib.auth import get_user_model
from openwisp_users.models import Organization
from django.db import transaction

from .settings import MONITORING_TIMESERIES_RETRY_OPTIONS

logger = logging.getLogger(__name__)


def transaction_on_commit(func):
    with transaction.atomic():
        transaction.on_commit(func)


def _get_org(self):
    org_name = 'Test Organization'
    user_model = get_user_model()
    admin = user_model.objects.create_superuser('admin', 'admin@example.com', 'admin')
    return Organization.objects.create(name=org_name, owner=admin)


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
