import json
import logging

from celery import shared_task
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured, ObjectDoesNotExist
from swapper import load_model

from .settings import CHECKS_LIST, IPERF_CHECK_CONFIG, IPERF_CHECK_LOCK_EXPIRE

logger = logging.getLogger(__name__)


def get_check_model():
    return load_model('check', 'Check')


def _run_iperf_check_on_multiple_servers(uuid, check):  # pragma: no cover
    """
    This will ensure that we only run iperf checks on those servers
    which are currently available for that organisation at that time,
    e.g. if orgA has ['iperf_server_1', 'iperf_server_2'], then one check
    will be run on each of them at the same time. If we receive the same
    task to run_iperf_check, then it should be pushed back to the queue
    and will be executed only after the completion of the current running tasks
    """
    lock_acquired = False
    org = check.content_object.organization
    if not IPERF_CHECK_CONFIG:
        logger.warning(
            f'Iperf check configuration for organization "{org}" is missing, {check} skipped!'
        )
        return

    iperf_config = IPERF_CHECK_CONFIG.get(str(org.id))
    iperf_servers = iperf_config.get('host')

    if not iperf_servers:
        logger.warning(
            f'The organization "{org}" iperf servers cannot be "{iperf_servers}", {check} skipped!'
        )
        return

    iperf_check = check.check_instance
    available_iperf_servers = iperf_check._get_param('host', 'host.default')
    iperf_check_time = iperf_check._get_param(
        'client_options.time', 'client_options.properties.time.default'
    )

    # Try to acquire a lock, or put task back on queue
    for server in available_iperf_servers:
        server_lock_key = f'ow_monitoring_{org}_iperf_check_{server}'
        # Set available_iperf_server to the org device
        # this cache key value will be used within iperf_check
        lock_acquired = cache.set(
            server_lock_key,
            str(check.content_object),
            timeout=IPERF_CHECK_LOCK_EXPIRE,
            nx=True,
        )
        if lock_acquired:
            break

    if not lock_acquired:
        logger.warning(
            (
                f'At the moment, all available iperf servers of organization "{org}" '
                f'are busy running checks, putting "{check}" back in the queue..'
            )
        )
        # Return the iperf_check task to the queue,
        # it comes back every 2*iperf_check_time (TCP+UDP)
        perform_check.apply_async(args=[uuid], countdown=2 * iperf_check_time)
        return
    try:
        # Execute iperf check
        result = check.perform_check()
    finally:
        # Release the lock after completion of the check
        cache.delete(server_lock_key)
    return result


@shared_task
def run_checks(checks=None):
    """
    Retrieves the id of all active checks in chunks of 2000 items
    and calls the ``perform_check`` task (defined below) for each of them.

    This allows to enqueue all the checks that need to be performed
    and execute them in parallel with multiple workers if needed.
    """
    # If checks is None, We should execute all the checks
    if checks is None:
        checks = CHECKS_LIST

    if not isinstance(checks, list):
        raise ImproperlyConfigured(
            f'Check path {checks} should be of type "list"'
        )  # pragma: no cover
    if not all(check_path in CHECKS_LIST for check_path in checks):
        raise ImproperlyConfigured(
            f'Check path {checks} should be in {CHECKS_LIST}'
        )  # pragma: no cover

    iterator = (
        get_check_model()
        .objects.filter(is_active=True, check_type__in=checks)
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
    if check.check_type in [
        'openwisp_monitoring.check.classes.Iperf'
    ]:  # pragma: no cover
        result = _run_iperf_check_on_multiple_servers(uuid, check)
    else:
        result = check.perform_check()
    if settings.DEBUG and result:  # pragma: nocover
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
def auto_create_iperf_check(
    model, app_label, object_id, check_model=None, content_type_model=None
):
    """
    Called by openwisp_monitoring.check.models.auto_iperf_check_receiver
    """
    Check = check_model or get_check_model()
    iperf_check_path = 'openwisp_monitoring.check.classes.Iperf'
    has_check = Check.objects.filter(
        object_id=object_id, content_type__model='device', check_type=iperf_check_path
    ).exists()
    # create new check only if necessary
    if has_check:
        return
    content_type_model = content_type_model or ContentType
    ct = content_type_model.objects.get(app_label=app_label, model=model)
    check = Check(
        name='Iperf',
        check_type=iperf_check_path,
        content_type=ct,
        object_id=object_id,
    )
    check.full_clean()
    check.save()
