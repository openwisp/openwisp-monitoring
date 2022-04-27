import logging

from swapper import load_model

from openwisp_monitoring.db.backends import timeseries_db

SELECT_QUERY_LIMIT = 1000
WRITE_BATCH_SIZE = 1000
READ_QUERY = (
    "SELECT {fields} FROM {measurement}"
    " WHERE content_type='{content_type_key}'"
    " AND object_id='{object_id}'"
)
DELETE_QUERY = (
    "DELETE FROM {old_measurement}"
    " WHERE content_type='{content_type_key}'"
    " AND object_id='{object_id}'"
)
CHUNK_SIZE = 1000

logger = logging.getLogger(__name__)


def get_writable_data(read_data, tags, old_measurement, new_measurement):
    """
    Prepares data that can be written by "timeseries_db.db.write_points"
    """
    write_data = []
    for data_point in read_data.get_points(measurement=old_measurement):
        data = {
            'time': data_point.pop('time'),
            'measurement': new_measurement,
            'tags': tags,
        }
        data['fields'] = data_point
        write_data.append(data)
    return write_data


def migrate_influxdb_data(
    configuration,
    new_measurement,
    read_query=READ_QUERY,
    delete_query=DELETE_QUERY,
):
    Metric = load_model('monitoring', 'Metric')
    metric_qs = Metric.objects.filter(
        configuration=configuration, extra_tags__contains='old_key', key=new_measurement
    )
    updated_metrics = []
    for metric in metric_qs.iterator(chunk_size=CHUNK_SIZE):
        old_measurement = metric.extra_tags.pop('old_key')
        fields = ','.join(['time', metric.field_name, *metric.related_fields])
        query = (f"{read_query} ORDER BY time ASC LIMIT {SELECT_QUERY_LIMIT}").format(
            fields=fields,
            measurement=old_measurement,
            content_type_key=metric.content_type_key,
            object_id=metric.object_id,
        )
        # Read and write data in batches to avoid loading
        # all data in memory at once.
        offset = 0
        read_data = timeseries_db.query(query, epoch='s')
        while read_data:
            write_data = get_writable_data(
                read_data, metric.tags, old_measurement, new_measurement=new_measurement
            )
            response = timeseries_db.db.write_points(
                write_data, tags=metric.tags, batch_size=WRITE_BATCH_SIZE
            )
            if response is True:
                offset += SELECT_QUERY_LIMIT
            else:
                logger.error(
                    'Error encountered in writing data to InfluxDB: {0}'.format(
                        response['error']
                    ),
                )
            read_data = timeseries_db.query(f'{query} OFFSET {offset}', epoch='s')

        # Delete data that has been migrated
        timeseries_db.query(
            delete_query.format(
                old_measurement=old_measurement,
                content_type_key=metric.content_type_key,
                object_id=metric.object_id,
            )
        )
        updated_metrics.append(metric)
        if len(updated_metrics) > CHUNK_SIZE:
            Metric.objects.bulk_update(updated_metrics, fields=['extra_tags'])
            updated_metrics = []
    if updated_metrics:
        Metric.objects.bulk_update(updated_metrics, fields=['extra_tags'])


def migrate_wifi_clients():
    read_query = f"{READ_QUERY} AND clients != ''"
    delete_query = f"{DELETE_QUERY} AND clients != ''"
    migrate_influxdb_data(
        new_measurement='wifi_clients',
        configuration='clients',
        read_query=read_query,
        delete_query=delete_query,
    )


def migrate_traffic_data():
    migrate_influxdb_data(new_measurement='traffic', configuration='traffic')


def migrate_influxdb_structure():
    # It is required to migrate "wifi_clients" metrics first
    # because InfluxDB cannot do comparison with NULL values.
    # Due to this, it is not possible to delete traffic rows from
    # the measurement without deleting wifi_clients rows.
    migrate_wifi_clients()
    migrate_traffic_data()
