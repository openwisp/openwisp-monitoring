from datetime import timezone
import os

from celery import shared_task
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from swapper import load_model

from openwisp_utils.tasks import OpenwispCeleryTask

from openwisp_monitoring.db.backends.influxdb.client import DatabaseClient as InfluxDB1Client
from openwisp_monitoring.db.backends.influxdb2.client import DatabaseClient as InfluxDB2Client

from ..db import timeseries_db
from ..db.exceptions import TimeseriesWriteException
from .migrations.influxdb import influxdb_alter_structure_0006 as influxdb_migration
from .migrations.influxdb2 import influxdb2_alter_structure_0006 as influxdb2_migration
from .settings import RETRY_OPTIONS
from .signals import post_metric_write
from openwisp_monitoring.db.backends.influxdb.client import DatabaseClient as InfluxDB1Client
from openwisp_monitoring.db.backends.influxdb2.client import DatabaseClient as InfluxDB2Client
from django.utils.dateparse import parse_date



def _metric_post_write(name, values, metric, check_threshold_kwargs, **kwargs):
    if not metric or not check_threshold_kwargs:
        return
    try:
        Metric = load_model('monitoring', 'Metric')
        if not isinstance(metric, Metric):
            metric = Metric.objects.select_related('alertsettings').get(pk=metric)
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


@shared_task(
    base=OpenwispCeleryTask,
    bind=True,
    autoretry_for=(TimeseriesWriteException,),
    **RETRY_OPTIONS
)
def timeseries_write(
    self, name, values, metric=None, check_threshold_kwargs=None, **kwargs
):
    """
    write with exponential backoff on a failure
    """
    timeseries_db.write(name, values, **kwargs)
    _metric_post_write(name, values, metric, check_threshold_kwargs, **kwargs)


def _timeseries_write(name, values, metric=None, check_threshold_kwargs=None, **kwargs):
    """
    If the timeseries database is using UDP to write data,
    then write data synchronously.
    """
    if hasattr(timeseries_db, 'use_udp') and timeseries_db.use_udp:
        # InfluxDB 1.x with UDP support
        func = timeseries_write
        args = (name, values, metric, check_threshold_kwargs)
    elif hasattr(timeseries_db, 'write'):
        # InfluxDB 2.0 or InfluxDB 1.x without UDP support
        func = timeseries_db.write(name, values, **kwargs)
        _metric_post_write(name, values, metric, check_threshold_kwargs, **kwargs)
    else:
        # Fallback to delayed write for other cases
        func = timeseries_write.delay
        metric = metric.pk if metric else None
        args = (name, values, metric, check_threshold_kwargs)


@shared_task(
    base=OpenwispCeleryTask,
    bind=True,
    autoretry_for=(TimeseriesWriteException,),
    **RETRY_OPTIONS
)
def timeseries_batch_write(self, data):
    """
    Similar to timeseries_write function above, but operates on
    list of metric data (batch operation)
    """
    timeseries_db.batch_write(data)
    for metric_data in data:
        _metric_post_write(**metric_data)


def _timeseries_batch_write(data):
    """
    If the timeseries database is using UDP to write data,
    then write data synchronously.
    """
    if timeseries_db.use_udp:
        timeseries_batch_write(data=data)
    else:
        for item in data:
            item['metric'] = item['metric'].pk
        timeseries_batch_write.delay(data=data)


@shared_task(base=OpenwispCeleryTask)
def delete_timeseries(key, tags):
    backend = settings.TIMESERIES_DATABASE['BACKEND']

    if backend == 'openwisp_monitoring.db.backends.influxdb':
        # InfluxDB 1.x
        client = InfluxDB1Client()
        client.delete_series(key=key, tags=tags)
    elif backend == 'openwisp_monitoring.db.backends.influxdb2':
        # InfluxDB 2.x
        # No need to perform any action for InfluxDB 2.x
        pass
    else:
        raise ValueError(f"Unsupported backend: {backend}")

@shared_task
def migrate_timeseries_database():
    """
    Perform migrations on timeseries database
    asynchronously for changes introduced in
    https://github.com/openwisp/openwisp-monitoring/pull/368

    To be removed in 1.1.0 release.
    """
    if os.environ.get('USE_INFLUXDB2', 'False') == 'True':
        influxdb2_migration.migrate_influxdb_structure()
    else:
        influxdb_migration.migrate_influxdb_structure()
