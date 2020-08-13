import logging

from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist
from swapper import load_model

from ..check.tasks import perform_check

logger = logging.getLogger(__name__)


@shared_task
def trigger_device_checks(pk, recovery=True):
    """
    Retrieves all related checks to the passed ``device``
    and calls the ``perform_check`` task from each of them.
    If no check exists changes the status according to the
    ``recovery`` argument.
    """
    DeviceData = load_model('device_monitoring', 'DeviceData')
    try:
        device = DeviceData.objects.get(pk=pk)
    except ObjectDoesNotExist:
        logger.warning(f'The device with uuid {pk} has been deleted')
        return
    checks = device.checks.filter(is_active=True).only('id').values('id')
    has_checks = False
    for check in checks:
        perform_check.delay(check['id'])
        has_checks = True
    if not has_checks:
        status = 'ok' if recovery else 'critical'
        device.monitoring.update_status(status)
