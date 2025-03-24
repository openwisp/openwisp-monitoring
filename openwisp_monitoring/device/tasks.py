import logging
import warnings

from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist
from django.utils.timezone import now, timedelta
from swapper import load_model

from openwisp_utils.tasks import OpenwispCeleryTask

from ..check.tasks import perform_check

logger = logging.getLogger(__name__)


@shared_task(base=OpenwispCeleryTask)
def trigger_device_critical_checks(pk, recovery=True):
    """Triggers the monitoring checks for the specified device pk.

    Retrieves all related checks to the passed ``device`` and calls the
    ``perform_check`` task from each of them.

    If no check exists changes the status according to the ``recovery``
    argument.
    """
    DeviceData = load_model('device_monitoring', 'DeviceData')
    try:
        device = DeviceData.objects.select_related('monitoring').get(pk=pk)
    except ObjectDoesNotExist:
        logger.warning(f'The device with uuid {pk} has been deleted')
        return
    check_ids = list(
        device.checks.filter(
            is_active=True, check_type__in=device.monitoring.get_critical_checks()
        ).values_list('id', flat=True)
    )
    if not check_ids:
        status = 'ok' if recovery else 'critical'
        device.monitoring.update_status(status)
        return
    if recovery and device.monitoring.status == 'critical':
        device.monitoring.update_status('problem')
    for check_id in check_ids:
        perform_check.delay(check_id)


@shared_task(base=OpenwispCeleryTask)
def trigger_device_checks(pk, recovery=True):
    """
    Deprecated, use trigger_device_critical_checks instead.
    """
    warnings.warn(
        'trigger_device_checks is deprecated, use trigger_device_critical_checks instead.',
        DeprecationWarning,
        stacklevel=2,
    )
    trigger_device_critical_checks(pk, recovery)


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
