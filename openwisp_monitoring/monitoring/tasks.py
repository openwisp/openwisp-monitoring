from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist
from swapper import load_model

from openwisp_utils.tasks import OpenwispCeleryTask

from ..db import timeseries_db
from ..db.exceptions import TimeseriesWriteException
from ..utils import is_monitoring_blocked
from .settings import RETRY_OPTIONS
from .signals import post_metric_write


def _get_metric(metric):
    if not metric:
        return None
    Metric = load_model("monitoring", "Metric")
    if isinstance(metric, Metric):
        return metric
    try:
        return Metric.objects.select_related("alertsettings").get(pk=metric)
    except ObjectDoesNotExist:
        return None


def _metric_post_write(name, values, metric, check_threshold_kwargs=None, **kwargs):
    if not metric or not check_threshold_kwargs:
        return
    metric = _get_metric(metric)
    if metric is None:
        # The metric can be deleted by the time threshold is being checked.
        # This can happen as the task is being run async.
        return
    metric.check_threshold(**check_threshold_kwargs)
    signal_kwargs = dict(
        sender=metric.__class__,
        metric=metric,
        values=values,
        time=kwargs.get("timestamp"),
        current=kwargs.get("current", "False"),
    )
    post_metric_write.send(**signal_kwargs)


@shared_task(
    base=OpenwispCeleryTask,
    bind=True,
    autoretry_for=(TimeseriesWriteException,),
    **RETRY_OPTIONS,
)
def timeseries_write(
    self, name, values, metric=None, check_threshold_kwargs=None, **kwargs
):
    """Writes and retries with exponential backoff on failures."""
    metric = _get_metric(metric)
    if metric is not None and is_monitoring_blocked(metric.content_object):
        return
    timeseries_db.write(name, values, **kwargs)
    _metric_post_write(name, values, metric, check_threshold_kwargs, **kwargs)


def _timeseries_write(name, values, metric=None, check_threshold_kwargs=None, **kwargs):
    """Handles writes synchronously when using UDP mode."""
    if timeseries_db.use_udp:
        func = timeseries_write
    else:
        func = timeseries_write.delay
        metric = metric.pk if metric else None
    func(
        name=name,
        values=values,
        metric=metric,
        check_threshold_kwargs=check_threshold_kwargs,
        **kwargs,
    )


def _filter_blocked_batch_data(data):
    """Drops entries whose target is blocked, checking each unique target once."""
    Metric = load_model("monitoring", "Metric")
    pks_to_fetch = {
        metric_data["metric"]
        for metric_data in data
        if metric_data.get("metric") and not isinstance(metric_data["metric"], Metric)
    }
    fetched_metrics = Metric.objects.in_bulk(pks_to_fetch) if pks_to_fetch else {}
    blocked_targets = {}
    filtered_data = []
    for metric_data in data:
        raw_metric = metric_data.get("metric")
        metric = (
            raw_metric
            if isinstance(raw_metric, Metric)
            else fetched_metrics.get(raw_metric)
        )
        if metric is None:
            filtered_data.append(metric_data)
            continue
        target_key = (metric.content_type_id, metric.object_id)
        if target_key not in blocked_targets:
            blocked_targets[target_key] = is_monitoring_blocked(metric.content_object)
        if not blocked_targets[target_key]:
            filtered_data.append(metric_data)
    return filtered_data


@shared_task(
    base=OpenwispCeleryTask,
    bind=True,
    autoretry_for=(TimeseriesWriteException,),
    **RETRY_OPTIONS,
)
def timeseries_batch_write(self, data):
    """Writes data in batches.

    Similar to timeseries_write function above, but operates on list of
    metric data (batch operation)
    """
    if not data:
        return
    data = _filter_blocked_batch_data(data)
    if not data:
        return
    timeseries_db.batch_write(data)
    for metric_data in data:
        _metric_post_write(**metric_data)


def _timeseries_batch_write(data):
    """If the timeseries database is using UDP to write data, then write data synchronously."""
    if timeseries_db.use_udp:
        timeseries_batch_write(data=data)
    else:
        for item in data:
            item["metric"] = item["metric"].pk
        timeseries_batch_write.delay(data=data)


@shared_task(base=OpenwispCeleryTask)
def delete_timeseries(key, tags):
    timeseries_db.delete_series(key=key, tags=tags)


@shared_task
def migrate_timeseries_database():
    """Performs migrations of timeseries datab.

    Performed asynchronously, due to changes introduced in
    https://github.com/openwisp/openwisp-monitoring/pull/368

    To be removed in a future release.
    """
    from .migrations.influxdb.influxdb_alter_structure_0006 import (
        migrate_influxdb_structure,
    )

    migrate_influxdb_structure()
