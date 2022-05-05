from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist
from swapper import load_model

from ..db import timeseries_db
from ..db.exceptions import TimeseriesWriteException
from .settings import RETRY_OPTIONS
from .signals import post_metric_write


@shared_task(bind=True, autoretry_for=(TimeseriesWriteException,), **RETRY_OPTIONS)
def timeseries_write(
    self, name, values, metric_pk=None, check_threshold_kwargs=None, **kwargs
):
    """
    write with exponential backoff on a failure
    """
    timeseries_db.write(name, values, **kwargs)
    if not metric_pk or not check_threshold_kwargs:
        return
    try:
        metric = load_model('monitoring', 'Metric').objects.get(pk=metric_pk)
    except ObjectDoesNotExist:
        # The metric can be deleted by the time threshold is being checked.
        # This can happen as the task is being run async.
        pass
    else:
        metric.check_threshold(**check_threshold_kwargs)
        signal_kwargs = dict(
            sender=metric.__class__,
            metric=metric,
            values=values,
            time=kwargs.get('timestamp'),
            current=kwargs.get('current', 'False'),
        )
        post_metric_write.send(**signal_kwargs)


@shared_task
def migrate_timeseries_database():
    """
    Perform migrations on timeseries database
    asynchronously for changes introduced in
    https://github.com/openwisp/openwisp-monitoring/pull/368

    To be removed in 1.1.0 release.
    """
    from .migrations.influxdb.influxdb_alter_structure_0006 import (
        migrate_influxdb_structure,
    )

    migrate_influxdb_structure()
