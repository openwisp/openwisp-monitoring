import logging

from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist
from django.utils.timezone import now, timedelta
from swapper import load_model

from openwisp_utils.tasks import OpenwispCeleryTask

from ..check.tasks import perform_check

logger = logging.getLogger(__name__)


@shared_task(base=OpenwispCeleryTask)
def trigger_device_checks(pk, recovery=True):
    """Triggers the monitoring checks for the specified device pk.

    Retrieves all related checks to the passed ``device`` and calls the
    ``perform_check`` task from each of them.

    If no check exists changes the status according to the ``recovery``
    argument.
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


@shared_task(base=OpenwispCeleryTask)
def delete_wifi_clients_and_sessions(days=6 * 30):
    WifiClient = load_model('device_monitoring', 'WifiClient')
    WifiSession = load_model('device_monitoring', 'WifiSession')

    WifiSession.objects.filter(start_time__lte=(now() - timedelta(days=days))).delete()
    WifiClient.objects.exclude(
        mac_address__in=WifiSession.objects.values_list('wifi_client')
    ).delete()


@shared_task(base=OpenwispCeleryTask)
def offline_device_close_session(device_id):
    WifiSession = load_model('device_monitoring', 'WifiSession')
    WifiSession.objects.filter(device_id=device_id, stop_time__isnull=True).update(
        stop_time=now()
    )


@shared_task(base=OpenwispCeleryTask)
def write_device_metrics(pk, data, time=None, current=False):
    DeviceData = load_model('device_monitoring', 'DeviceData')
    try:
        device_data = DeviceData.get_devicedata(str(pk))
    except DeviceData.DoesNotExist:
        return
    device_data.writer.write(data, time, current)


@shared_task(base=OpenwispCeleryTask)
def handle_disabled_organization(organization_id):
    DeviceMonitoring = load_model('device_monitoring', 'DeviceMonitoring')
    DeviceMonitoring.handle_disabled_organization(organization_id)
