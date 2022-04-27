# Manually created

import logging

from django.core.exceptions import ObjectDoesNotExist
from django.db import migrations
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


def get_writable_data(read_data, metric, new_measurement):
    write_data = []
    for data_point in read_data.get_points(measurement=metric.key):
        data = {
            'time': data_point.pop('time'),
            'measurement': new_measurement,
            'tags': metric.tags,
        }
        data['fields'] = data_point
        write_data.append(data)
    return write_data


def migrate_influxdb_data(
    new_measurement, metric_qs, read_query=READ_QUERY, delete_query=DELETE_QUERY
):
    for metric in metric_qs.exclude(key__in=EXCLUDED_MEASUREMENTS).iterator():
        extra_tags = {'ifname': metric.key}
        try:
            extra_tags.update(
                {'organization_id': str(metric.content_object.organization_id)}
            )
        except ObjectDoesNotExist:
            pass
        metric.extra_tags.update(extra_tags)
        measurement = metric.key.replace('-', '_')
        fields = ','.join(['time', metric.field_name, *metric.related_fields])
        query = (f"{read_query} ORDER BY time ASC LIMIT {SELECT_QUERY_LIMIT}").format(
            fields=fields,
            measurement=measurement,
            content_type_key=metric.content_type_key,
            object_id=metric.object_id,
        )
        # Read and write data in batches to avoid loading
        # all data in memory at once.
        offset = 0
        read_data = timeseries_db.query(query, epoch='s')
        while read_data:
            write_data = get_writable_data(
                read_data, metric, new_measurement=new_measurement
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
                old_measurement=measurement,
                content_type_key=metric.content_type_key,
                object_id=metric.object_id,
            )
        )
        metric.key = new_measurement
        metric.save()


def migrate_wifi_clients():
    Metric = load_model('monitoring', 'Metric')
    read_query = f"{READ_QUERY} AND clients != ''"
    delete_query = f"{DELETE_QUERY} AND clients != ''"
    metric_qs = Metric.objects.filter(configuration='clients')
    migrate_influxdb_data(
        new_measurement='wifi_clients',
        metric_qs=metric_qs,
        read_query=read_query,
        delete_query=delete_query,
    )


def migrate_traffic_data():
    Metric = load_model('monitoring', 'Metric')
    metric_qs = Metric.objects.filter(configuration='traffic')
    migrate_influxdb_data(new_measurement='traffic', metric_qs=metric_qs)


def migrate_influxdb_structure(apps, schema_editor):
    migrate_wifi_clients()
    migrate_traffic_data()


def reverse_migration(apps, schema_editor):
    Metric = load_model('monitoring', 'Metric')
    for metric in Metric.objects.filter(key='traffic').iterator():
        metric.key = metric.extra_tags['ifname']
        metric.save()


class Migration(migrations.Migration):

    dependencies = [('monitoring', '0004_metric_extra_tags')]

    operations = [
        migrations.RunPython(migrate_influxdb_structure, reverse_code=reverse_migration)
    ]
