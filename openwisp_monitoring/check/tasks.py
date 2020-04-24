import json

from celery import shared_task
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from swapper import load_model


@shared_task
def run_checks():
    """
    Retrieves the id of all active checks in chunks of 2000 items
    and calls the ``perform_check`` task (defined below) for each of them.

    This allows to enqueue all the checks that need to be performed
    and execute them in parallel with multiple workers if needed.
    """
    Check = load_model('check', 'Check')
    iterator = Check.objects.filter(active=True).only('id').values('id').iterator()
    for check in iterator:
        perform_check.delay(check['id'])


@shared_task
def perform_check(uuid):
    """
    Retrieves check according to the passed UUID
    and calls ``check.perform_check()``
    """
    Check = load_model('check', 'Check')
    check = Check.objects.get(pk=uuid)
    result = check.perform_check()
    if settings.DEBUG:  # pragma: nocover
        print(json.dumps(result, indent=4, sort_keys=True))


@shared_task
def auto_create_ping(model, app_label, object_id, created):
    """
    Called by openwisp_monitoring.check.models.auto_ping_receiver
    """
    Check = load_model('check', 'Check')
    ping_path = 'openwisp_monitoring.check.classes.Ping'
    has_check = (
        Check.objects.filter(
            object_id=object_id, content_type__model='device', check=ping_path
        ).count()
        > 0
    )
    # create new check only if necessary
    if has_check:
        return
    ct = ContentType.objects.get(app_label=app_label, model=model)
    check = Check(name='Ping', check=ping_path, content_type=ct, object_id=object_id)
    check.full_clean()
    check.save()
