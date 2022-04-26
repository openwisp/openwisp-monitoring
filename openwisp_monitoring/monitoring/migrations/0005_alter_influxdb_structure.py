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
    " ORDER BY time ASC"
    f" LIMIT {SELECT_QUERY_LIMIT}"
)

DELETE_QUERY = (
    "DELETE FROM {old_measurement}"
    " WHERE content_type='{content_type_key}'"
    " AND object_id='{object_id}'"
)

logger = logging.getLogger(__name__)


def get_all_measurements():
    measurements = []
    for measurement in timeseries_db.db.get_list_measurements():
        measurements.append(measurement['name'])
    return measurements


def get_interface_measurements():
    """
    Interface names can be anything. Therefore instead of
    performing migrations for common interface names
    (e.g. lan, eth0, tun0, etc.), exclude measurements that
    are used by openwisp-monitoring for other metrics. The
    remaining measurements are assumed to be related to traffic.
    """
    excluded_measurements = [
        'ping',
        'config_applied',
        'clients',
        'disk',
        'memory',
        'cpu',
        'signal_strength',
        'signal_quality',
        'access_tech',
    ]
    interface_measurements = []
    for measurement in get_all_measurements():
        if measurement not in excluded_measurements:
            interface_measurements.append(measurement)
    return interface_measurements


def get_writable_data(read_data, metric):
    write_data = []
    for data_point in read_data.get_points(measurement=metric.key):
        data = {
            'time': data_point.pop('time'),
            'measurement': 'traffic',
            'tags': metric.tags,
        }
        data['fields'] = data_point
        write_data.append(data)
    return write_data


def merge_interface_traffic_measurement(apps, schema_editor):
    Metric = load_model('monitoring', 'Metric')
    interface_measurements = get_interface_measurements()
    for measurement in interface_measurements:
        for metric in Metric.objects.filter(key=measurement).iterator():
            extra_tags = {'ifname': metric.key}
            try:
                extra_tags.update(
                    {'organization_id': str(metric.content_object.organization_id)}
                )
            except ObjectDoesNotExist:
                pass
            metric.extra_tags.update(extra_tags)
            fields = ','.join(['time', metric.field_name, *metric.related_fields])
            query = READ_QUERY.format(
                fields=fields,
                measurement=metric.key,
                content_type_key=metric.content_type_key,
                object_id=metric.object_id,
            )
            # Read and write data in batches to avoid loading
            # all data in memory at once.
            offset = 0
            read_data = timeseries_db.query(query, epoch='s')
            while read_data:
                write_data = get_writable_data(read_data, metric)
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
                DELETE_QUERY.format(
                    old_measurement=extra_tags['ifname'],
                    content_type_key=metric.content_type_key,
                    object_id=metric.object_id,
                )
            )


class Migration(migrations.Migration):

    dependencies = [('monitoring', '0004_metric_extra_tags')]

    operations = [
        migrations.RunPython(
            merge_interface_traffic_measurement, reverse_code=migrations.RunPython.noop
        )
    ]
