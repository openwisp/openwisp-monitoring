import logging
import time

import requests
from django.core.exceptions import ObjectDoesNotExist
from influxdb.exceptions import InfluxDBServerError
from swapper import load_model

from openwisp_monitoring.db.backends import timeseries_db
from openwisp_monitoring.db.exceptions import TimeseriesWriteException

SELECT_QUERY_LIMIT = 1000
WRITE_BATCH_SIZE = 1000
READ_QUERY = (
    "SELECT {fields} FROM {measurement}"
    " WHERE content_type='{content_type_key}'"
    " AND object_id='{object_id}'"
)
DELETE_QUERY = (
    "DROP SERIES FROM {old_measurement}"
    " WHERE content_type='{content_type_key}'"
    " AND object_id='{object_id}'"
)
CHUNK_SIZE = 1000
EXCLUDED_MEASUREMENTS = [
    'ping',
    'config_applied',
    'clients',
    'disk',
    'memory',
    'cpu',
    'signal_strength',
    'signal_quality',
    'access_tech',
    'device_data',
    'traffic',
    'wifi_clients',
]

logger = logging.getLogger(__name__)


def get_writable_data(read_data, tags, old_measurement, new_measurement):
    """Prepares data that can be written by "timeseries_db.db.write_points"."""
    write_data = []
    for data_point in read_data.get_points(measurement=old_measurement):
        data = {
            'time': data_point.pop('time'),
            'measurement': new_measurement,
            'tags': tags,
        }
        data['fields'] = data_point
        write_data.append(data)
    return write_data, len(write_data)


def retry_until_success(func, *args, **kwargs):
    sleep_time = 1
    while True:
        try:
            return func(*args, **kwargs)
        except (
            requests.exceptions.ConnectionError,
            TimeseriesWriteException,
            InfluxDBServerError,
            timeseries_db.client_error,
        ) as error:
            if 'points beyond retention policy dropped' in str(error):
                # When writing data to the InfluxDB, if the measurement
                # points are older than the retention policy the
                # InfluxDB returns a HTTP 400 response. Retrying this
                # operation will again result in HTTP 400, hence
                # this error is assumed as success.
                return True
            sleep_time *= 2
            time.sleep(sleep_time)
            logger.warning(
                (
                    f'Error encountered while executing {func.__name__}'
                    f' with args: {args} and kwargs: {kwargs}.\n'
                    f'Retrying after {sleep_time} seconds.\n'
                    f'Error: {error}'
                )
            )
            continue


def migrate_influxdb_data(
    configuration,
    new_measurement,
    read_query=READ_QUERY,
    delete_query=DELETE_QUERY,
):
    Metric = load_model('monitoring', 'Metric')
    metric_qs = Metric.objects.filter(configuration=configuration, key=new_measurement)
    for metric in metric_qs.iterator(chunk_size=CHUNK_SIZE):
        old_measurement = metric.main_tags.get('ifname')
        fields = ','.join(['time', metric.field_name, *metric.related_fields])
        query = (f"{read_query} ORDER BY time DESC LIMIT {SELECT_QUERY_LIMIT}").format(
            fields=fields,
            measurement=old_measurement,
            content_type_key=metric.content_type_key,
            object_id=metric.object_id,
        )
        # Read and write data in batches to avoid loading
        # all data in memory at once.
        offset = 0
        migrated_rows = 0
        read_data = retry_until_success(timeseries_db.query, query, epoch='s')
        while read_data:
            write_data, write_data_count = get_writable_data(
                read_data, metric.tags, old_measurement, new_measurement=new_measurement
            )
            start = offset
            end = offset + min(write_data_count, SELECT_QUERY_LIMIT)
            response = retry_until_success(
                timeseries_db.db.write_points,
                write_data,
                tags=metric.tags,
                batch_size=WRITE_BATCH_SIZE,
            )
            if response is True:
                logger.info(
                    f'Successfully written rows for "{metric} (id:{metric.id})"'
                    f' from {start} to {end}.'
                )
                migrated_rows += write_data_count
                offset += SELECT_QUERY_LIMIT
            else:
                logger.warning(
                    f'Error encountered in writing data for "{metric} (id:{metric.id})"'
                    f' from {start} to {end}: {response["error"]}. It will be retried.'
                )
            read_data = retry_until_success(
                timeseries_db.query, f'{query} OFFSET {offset}', epoch='s'
            )
        logger.info(f'Migrated {migrated_rows} row(s) for "{metric} (id:{metric.id})".')

        # Delete data that has been migrated
        if delete_query:
            retry_until_success(
                timeseries_db.query,
                delete_query.format(
                    old_measurement=old_measurement,
                    content_type_key=metric.content_type_key,
                    object_id=metric.object_id,
                ),
            )
            logger.info(f'Deleted old measurements for "{metric} (id:{metric.id})".')


def migrate_wifi_clients():
    read_query = f"{READ_QUERY} AND clients != ''"
    # Lookup using fields not supported in WHERE clause during deletion.
    # Hence, we cannot perform delete operation only for rows that
    # contains clients.
    delete_query = None
    migrate_influxdb_data(
        new_measurement='wifi_clients',
        configuration='clients',
        read_query=read_query,
        delete_query=delete_query,
    )
    logger.info('"wifi_clients" measurements successfully migrated.')


def migrate_traffic_data():
    migrate_influxdb_data(
        new_measurement='traffic',
        configuration='traffic',
        delete_query=f"{DELETE_QUERY} AND access_tech != ''",
    )
    logger.info('"traffic" measurements successfully migrated.')


def migrate_signal_strength_data():
    migrate_influxdb_data(
        new_measurement='signal', configuration='signal_strength', delete_query=None
    )
    logger.info('"signal_strength" measurements successfully migrated.')


def migrate_signal_quality_data():
    migrate_influxdb_data(
        new_measurement='signal', configuration='signal_quality', delete_query=None
    )
    logger.info('"signal_quality" measurements successfully migrated.')


def migrate_access_tech_data():
    migrate_influxdb_data(
        new_measurement='signal',
        configuration='access_tech',
    )
    logger.info('"access_tech" measurements successfully migrated.')


def requires_migration():
    """Indicates whether influxdb data migration is necessary.

    Returns "False" if all measurements presents in InfluxDB are present
    in EXCLUDED_MEASUREMENTS. This means that there are no interface
    specific measurements. Otherwise, returns "True".
    """
    tsdb_measurements = timeseries_db.db.get_list_measurements()
    for measurement in tsdb_measurements:
        if measurement['name'] not in EXCLUDED_MEASUREMENTS:
            return True
    return False


def migrate_influxdb_structure():
    if not requires_migration():
        logger.info(
            'Timeseries data migration is already migrated. Skipping migration!'
        )
        return
    migrate_wifi_clients()
    migrate_traffic_data()
    migrate_signal_strength_data()
    migrate_signal_quality_data()
    migrate_access_tech_data()
    logger.info('Timeseries data migration completed.')


def _forward_migrate_metric(metric_model, configuration, new_key, add_org_tag=True):
    metric_qs = metric_model.objects.filter(configuration=configuration).exclude(
        key__in=EXCLUDED_MEASUREMENTS
    )
    updated_metrics = []
    for metric in metric_qs.iterator(chunk_size=CHUNK_SIZE):
        try:
            assert add_org_tag is True
            extra_tags = {'organization_id': str(metric.content_object.organization_id)}
        except (AssertionError, ObjectDoesNotExist):
            extra_tags = {}
        metric.main_tags = {
            'ifname': metric.key,
        }
        metric.extra_tags.update(extra_tags)
        metric.key = new_key
        updated_metrics.append(metric)
        if len(updated_metrics) > CHUNK_SIZE:
            metric_model.objects.bulk_update(
                updated_metrics, fields=['main_tags', 'extra_tags', 'key']
            )
            updated_metrics = []
    if updated_metrics:
        metric_model.objects.bulk_update(
            updated_metrics, fields=['main_tags', 'extra_tags', 'key']
        )


def update_metric_timeseries_structure_forward_migration(apps, schema_editor):
    """
    Updates metric objects to use static value for key and set
    interface name in the main tags
    """
    Metric = load_model('monitoring', 'Metric')
    _forward_migrate_metric(Metric, configuration='clients', new_key='wifi_clients')
    _forward_migrate_metric(Metric, configuration='traffic', new_key='traffic')
    _forward_migrate_metric(
        Metric, configuration='signal_strength', new_key='signal', add_org_tag=False
    )
    _forward_migrate_metric(
        Metric, configuration='signal_quality', new_key='signal', add_org_tag=False
    )
    _forward_migrate_metric(
        Metric, configuration='access_tech', new_key='signal', add_org_tag=False
    )


def update_metric_timeseries_structure_reverse_migration(
    apps, schema_editor, metric_keys=None
):
    """
    Reverse migration is required because of the
    the unique together condition implemented in
    Metric model.
    """
    Metric = load_model('monitoring', 'Metric')
    metric_keys = metric_keys or ['traffic', 'wifi_clients', 'signal']
    updated_metrics = []
    for metric in Metric.objects.filter(
        key__in=metric_keys,
    ).iterator(chunk_size=CHUNK_SIZE):
        metric.key = metric.main_tags['ifname']
        updated_metrics.append(metric)
        if len(updated_metrics) > CHUNK_SIZE:
            Metric.objects.bulk_update(updated_metrics, fields=['key'])
            updated_metrics = []
    if updated_metrics:
        Metric.objects.bulk_update(updated_metrics, fields=['key'])
