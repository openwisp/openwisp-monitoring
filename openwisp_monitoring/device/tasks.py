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


@shared_task(base=OpenwispCeleryTask)
def save_wifi_clients_and_sessions(device_data, device_pk):
    _WIFICLIENT_FIELDS = ['vendor', 'ht', 'vht', 'wmm', 'wds', 'wps']
    WifiClient = load_model('device_monitoring', 'WifiClient')
    WifiSession = load_model('device_monitoring', 'WifiSession')

    active_sessions = []
    interfaces = device_data.get('interfaces', [])
    for interface in interfaces:
        if interface.get('type') != 'wireless':
            continue
        interface_name = interface.get('name')
        wireless = interface.get('wireless', {})

        ssid = wireless.get('ssid')
        clients = wireless.get('clients', [])
        for client in clients:
            # Save WifiClient
            client_obj, created = WifiClient.objects.get_or_create(
                mac_address=client.get('mac')
            )
            update_fields = []
            for field in _WIFICLIENT_FIELDS:
                if getattr(client_obj, field) != client.get(field):
                    setattr(client_obj, field, client.get(field))
                    update_fields.append(field)
            if update_fields:
                client_obj.full_clean()
                client_obj.save(update_fields=update_fields)

            # Save WifiSession
            session_obj, _ = WifiSession.objects.get_or_create(
                device_id=device_pk,
                interface_name=interface_name,
                ssid=ssid,
                wifi_client=client_obj,
                stop_time=None,
            )
            active_sessions.append(session_obj.pk)

    # Close open WifiSession
    WifiSession.objects.filter(device_id=device_pk, stop_time=None,).exclude(
        pk__in=active_sessions
    ).update(stop_time=now())


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
        device_data = DeviceData.objects.get(id=pk)
    except DeviceData.DoesNotExist:
        return
    device_data.writer.write(data, time, current)
