import json
import logging
from time import monotonic

from celery import shared_task
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured, ObjectDoesNotExist
from redis import StrictRedis
from swapper import load_model

from .settings import CHECKS_LIST, IPERF_CHECK_CONFIG

logger = logging.getLogger(__name__)
# We need to be careful while utilising this time variable.
# lock expires in 25 secs, just greater than the TCP + UDP test time
CACHE_LOCK_EXPIRE = 25
# Todo: Update redis host
redis_client = StrictRedis('localhost', 6379, charset="utf-8", decode_responses=True)


def get_check_model():
    return load_model('check', 'Check')


def _run_iperf_check_on_multiple_servers(uuid, check):
    """
    This will ensure that we only run iperf checks on those servers
    which are currently available for that organisation at that time,
    e.g. if orgA has ['iperf_server_1', 'iperf_server_2'], then one check
    will be run on each of them at the same time. If we receive the same
    task to run_iperf_check, then it should be pushed back to the queue
    and will be executed only after the completion of the current running tasks
    """
    org_id = str(check.content_object.organization.id)
    iperf_config = IPERF_CHECK_CONFIG.get(org_id)
    iperf_servers = iperf_config.get('host')
    # To do: change the cache key id to be
    # device organisation specific, ie.check_id_org_id.
    check_lock_id = 'ow_monitoring_iperf_check_lock'
    available_iperf_servers_id = 'ow_monitoring_available_iperf_servers'
    if not iperf_config:
        logger.warning(
            (
                f'Iperf check config for organization {check.content_object.organization}'
                'is not defined in settings, iperf check skipped!'
            )
        )
        return
    if not iperf_servers:
        logger.warning(
            f'The organization iperf servers cannot be {iperf_servers}, iperf check skipped!'
        )
        return
    redis_client.set(
        available_iperf_servers_id, len(iperf_servers), ex=CACHE_LOCK_EXPIRE, nx=True
    )
    available_iperf_servers = int(redis_client.get(available_iperf_servers_id))
    # Timeout with a small diff, so we'll leave the lock delete
    # to the cache if it's close to being auto-removed/expired
    timeout_at = monotonic() + CACHE_LOCK_EXPIRE - 2.5
    # Try to acquire a lock, or put task back on queue
    lock_acquired = redis_client.set(
        check_lock_id, 'locked', ex=CACHE_LOCK_EXPIRE, nx=True
    )
    if not lock_acquired and not available_iperf_servers:
        logger.warning(
            f'The Iperf server is already occupied by a device, so putting {check} back in queue'
        )
        # We need to be careful while utilising this time variable
        # It should be greater or equal to 2*(TCP+UDP) test time
        perform_check.apply_async(args=[uuid], countdown=2 * 25)
        return
    try:
        # Execute iperf check & decrement current available_iperf_servers
        available_iperf_servers = int(redis_client.get(available_iperf_servers_id))
        redis_client.set(
            available_iperf_servers_id,
            available_iperf_servers - 1,
            ex=CACHE_LOCK_EXPIRE,
        )
        result = check.perform_check()
    finally:
        # Release the lock & increment current available_iperf_servers
        if monotonic() < timeout_at:
            redis_client.delete(check_lock_id)
            available_iperf_servers = int(redis_client.get(available_iperf_servers_id))
            redis_client.set(
                available_iperf_servers_id,
                available_iperf_servers + 1,
                ex=CACHE_LOCK_EXPIRE,
            )
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
    if check.check_type in ['openwisp_monitoring.check.classes.Iperf']:
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
