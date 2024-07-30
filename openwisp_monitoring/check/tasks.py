import json
import logging

from celery import shared_task
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured, ObjectDoesNotExist
from swapper import load_model

from openwisp_utils.tasks import OpenwispCeleryTask

from .settings import CHECKS_LIST

logger = logging.getLogger(__name__)


def get_check_model():
    return load_model('check', 'Check')


@shared_task(time_limit=2 * 60 * 60)
def run_checks(checks=None):
    """Runs all the checks.

    Retrieves the id of all active checks in chunks of 2000 items and
    calls the ``perform_check`` task (defined below) for each of them.

    This allows to enqueue all the checks that need to be performed and
    execute them in parallel with multiple workers if needed.
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


@shared_task(time_limit=30 * 60)
def perform_check(uuid):
    """Performs check with specified uuid.

    Retrieves check according to the passed UUID and calls the
    ``perform_check()`` method.
    """
    try:
        check = get_check_model().objects.get(pk=uuid)
    except ObjectDoesNotExist:
        logger.warning(f'The check with uuid {uuid} has been deleted')
        return
    result = check.perform_check()
    if settings.DEBUG:  # pragma: nocover
        print(json.dumps(result, indent=4, sort_keys=True))


@shared_task(base=OpenwispCeleryTask)
def auto_create_ping(
    model, app_label, object_id, check_model=None, content_type_model=None
):
    """Implements the auto creation of the ping check.

    Called by django signal (dispatch_uid: auto_ping) registered in check
    app's apps.py file.
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
    ct = content_type_model.objects.get_by_natural_key(app_label=app_label, model=model)
    check = Check(
        name='Ping', check_type=ping_path, content_type=ct, object_id=object_id
    )
    check.full_clean()
    check.save()


@shared_task(base=OpenwispCeleryTask)
def auto_create_config_check(
    model, app_label, object_id, check_model=None, content_type_model=None
):
    """Implements the auto creation of the config modified check.

    Called by openwisp_monitoring.check.models.auto_config_check_receiver.
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
    ct = content_type_model.objects.get_by_natural_key(app_label=app_label, model=model)
    check = Check(
        name='Configuration Applied',
        check_type=config_check_path,
        content_type=ct,
        object_id=object_id,
    )
    check.full_clean()
    check.save()


@shared_task(base=OpenwispCeleryTask)
def auto_create_iperf3_check(
    model, app_label, object_id, check_model=None, content_type_model=None
):
    """Implements the auto creation of the iperf3 check.

    Called by the
    openwisp_monitoring.check.models.auto_iperf3_check_receiver.
    """
    Check = check_model or get_check_model()
    iperf3_check_path = 'openwisp_monitoring.check.classes.Iperf3'
    has_check = Check.objects.filter(
        object_id=object_id, content_type__model='device', check_type=iperf3_check_path
    ).exists()
    # create new check only if necessary
    if has_check:
        return
    content_type_model = content_type_model or ContentType
    ct = content_type_model.objects.get_by_natural_key(app_label=app_label, model=model)
    check = Check(
        name='Iperf3',
        check_type=iperf3_check_path,
        content_type=ct,
        object_id=object_id,
    )
    check.full_clean()
    check.save()
