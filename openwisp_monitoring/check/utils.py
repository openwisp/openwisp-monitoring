from .tasks import run_checks, run_iperf_checks


def run_checks_async():
    """
    Calls celery task run_checks
    is run in a background worker
    """
    run_checks.delay()


def run_iperf_checks_async():
    """
    Calls celery task run_iperf_checks
    is run in a background worker
    """
    run_iperf_checks.delay()
