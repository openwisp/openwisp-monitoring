from __future__ import absolute_import, unicode_literals

import json

from celery import shared_task
from django.conf import settings

from .models import Check


@shared_task
def run_checks():
    """
    Retrieves the id of all active checks in chunks of 2000 items
    and calls the ``perform_check`` task (defined below) for each of them.

    This allows to enqueue all the checks that need to be performed
    and execute them in parallel with multiple worker if needed.
    """
    iterator = Check.objects.filter(active=True) \
                            .only('id') \
                            .values('id') \
                            .iterator()
    for check in iterator:
        perform_check.delay(check['id'])


@shared_task
def perform_check(uuid):
    """
    Retrieves check according to the passed UUID
    and calls ``check.perform_check()``
    """
    check = Check.objects.get(pk=uuid)
    result = check.perform_check()
    if settings.DEBUG:  # pragma: nocover
        print(json.dumps(result, indent=4, sort_keys=True))
