from celery import shared_task

from ..check.tasks import perform_check
from .models import DeviceData


@shared_task
def trigger_device_checks(pk):
    """
    Retrieves all related checks to the passed ``device``
    and calls the ``perform_check`` task from each of them.
    If no check exists changes the status to ``OK``.
    """
    device = DeviceData.objects.get(pk=pk)
    checks = device.checks.filter(active=True).only('id').values('id')
    for check in checks:
        perform_check.delay(check['id'])
    # if there's no available check for this device, we'll flag it as OK directly
    else:
        device.monitoring.update_status('ok')
