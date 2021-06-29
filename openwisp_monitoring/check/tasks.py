import json
import logging

from celery import shared_task
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from swapper import load_model

from openwisp_controller.connection import settings as app_settings

logger = logging.getLogger(__name__)


def get_check_model():
    return load_model('check', 'Check')


def _get_or_create_credentials(device_id, **kwargs):
    Credentials = load_model('connection', 'Credentials')
    cred = Credentials.objects.filter(
        deviceconnection__device_id=device_id,
        connector='openwisp_controller.connection.connectors.snmp.Snmp',
    ).last()
    if cred is not None:
        return cred

    # if credentials don't exist, create new SNMP credentials
    Device = load_model('config', 'Device')
    opts = dict(
        name='Default SNMP Credentials',
        connector=app_settings.DEFAULT_CONNECTORS[1][0],
        params={'community': 'public', 'agent': 'default', 'port': 161},
    )
    opts.update(kwargs)
    if 'organization' not in opts:
        opts['organization'] = Device.objects.get(id=device_id).organization
    c = Credentials(**opts)
    c.full_clean()
    c.save()
    return c


@shared_task
def run_checks():
    """
    Retrieves the id of all active checks in chunks of 2000 items
    and calls the ``perform_check`` task (defined below) for each of them.

    This allows to enqueue all the checks that need to be performed
    and execute them in parallel with multiple workers if needed.
    """
    iterator = (
        get_check_model()
        .objects.filter(is_active=True)
        .only('id')
        .values('id')
        .iterator()
    )
    for check in iterator:
        perform_check.delay(check['id'])


@shared_task
def perform_check(uuid):
    """
    Retrieves check according to the passed UUID
    and calls ``check.perform_check()``
    """
    try:
        check = get_check_model().objects.get(pk=uuid)
    except ObjectDoesNotExist:
        logger.warning(f'The check with uuid {uuid} has been deleted')
        return
    result = check.perform_check()
    if settings.DEBUG:  # pragma: nocover
        print(json.dumps(result, indent=4, sort_keys=True))


@shared_task
def auto_create_ping(
    model, app_label, object_id, check_model=None, content_type_model=None
):
    """
    Called by django signal (dispatch_uid: auto_ping)
    registered in check app's apps.py file.
    """
    Check = check_model or get_check_model()
    ping_path = 'openwisp_monitoring.check.classes.Ping'
    has_check = Check.objects.filter(
        object_id=object_id, content_type__model='device', check_type=ping_path
    ).exists()
    # create new check only if necessary
    if has_check:
        return
    content_type_model = content_type_model or ContentType
    ct = content_type_model.objects.get(app_label=app_label, model=model)
    check = Check(
        name='Ping', check_type=ping_path, content_type=ct, object_id=object_id
    )
    check.full_clean()
    check.save()


@shared_task
def auto_create_config_check(
    model, app_label, object_id, check_model=None, content_type_model=None
):
    """
    Called by openwisp_monitoring.check.models.auto_config_check_receiver
    """
    Check = check_model or get_check_model()
    config_check_path = 'openwisp_monitoring.check.classes.ConfigApplied'
    has_check = Check.objects.filter(
        object_id=object_id, content_type__model='device', check_type=config_check_path
    ).exists()
    # create new check only if necessary
    if has_check:
        return
    content_type_model = content_type_model or ContentType
    ct = content_type_model.objects.get(app_label=app_label, model=model)
    check = Check(
        name='Configuration Applied',
        check_type=config_check_path,
        content_type=ct,
        object_id=object_id,
    )
    check.full_clean()
    check.save()


@shared_task
def auto_create_snmp_devicemonitoring(
    model, app_label, object_id, check_model=None, content_type_model=None
):
    """
    Called by openwisp_monitoring.check.models.auto_snmp_devicemonitoring_receiver
    """
    Check = check_model or get_check_model()
    devicemonitoring_path = 'openwisp_monitoring.check.classes.SnmpDeviceMonitoring'
    has_check = Check.objects.filter(
        object_id=object_id, content_type__model='device', check=devicemonitoring_path
    ).exists()
    # create new check only if necessary
    if has_check:
        return
    content_type_model = content_type_model or ContentType
    ct = content_type_model.objects.get(app_label=app_label, model=model)
    cred = _get_or_create_credentials(object_id)
    check = Check(
        name='SNMP Device Monitoring',
        check=devicemonitoring_path,
        content_type=ct,
        object_id=object_id,
        params={'credential_params': cred.get_params()},
    )
    check.full_clean()
    check.save()
