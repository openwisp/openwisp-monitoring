from __future__ import absolute_import, unicode_literals

from .tasks import run_checks


def run_checks_async():
    """
    Calls celery task run_checks
    is run in a background worker
    """
    run_checks.delay()
