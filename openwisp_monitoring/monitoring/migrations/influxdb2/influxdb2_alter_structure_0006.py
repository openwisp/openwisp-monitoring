# openwisp_monitoring/monitoring/migrations/influxdb2/influxdb2_alter_structure_0006.py
import logging
from datetime import datetime, timedelta

from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
from swapper import load_model

from openwisp_monitoring.db.backends.influxdb2.client import DatabaseClient
from openwisp_monitoring.db.exceptions import TimeseriesWriteException

SELECT_QUERY_LIMIT = 1000
WRITE_BATCH_SIZE = 1000
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


def get_influxdb_client():
    db_config = {
        'bucket': 'mybucket',
        'org': 'myorg',
        'token': 'dltiEmsmMKU__9SoBE0ingFdMTS3UksrESwIQDNtW_3WOgn8bQGdyYzPcx_aDtvZkqvR8RbMkwVVlzUJxpm62w==',
        'url': 'http://localhost:8086',
    }
    return DatabaseClient(**db_config)


def requires_migration():
    client = get_influxdb_client()
    query_api = client.client.query_api()
    query = f'from(bucket: "{client.bucket}") |> range(start: -1h)'
    tsdb_measurements = query_api.query(org=client.org, query=query)
    for table in tsdb_measurements:
        for record in table.records:
            if record.get_measurement() not in EXCLUDED_MEASUREMENTS:
                return True
    return False


def migrate_influxdb_structure():
    if not requires_migration():
        logger.info(
            'Timeseries data migration is already migrated. Skipping migration!'
        )
        return

    # Implement your data migration logic here
    logger.info('Starting migration for InfluxDB 2.0...')
    migrate_wifi_clients()
    migrate_traffic_data()
    logger.info('Timeseries data migration completed.')


def migrate_influxdb_data(query_api, write_api, read_query, measurement, tags):
    logger.debug(f'Executing query: {read_query}')
    result = query_api.query(org='myorg', query=read_query)
    points = []

    for table in result:
        for record in table.records:
            point = {
                'measurement': measurement,
                'tags': tags,
                'fields': record.values,
                'time': record.get_time(),
            }
            points.append(point)

    write_api.write(
        bucket='mybucket', org='myorg', record=points, write_options=SYNCHRONOUS
    )
    logger.info(f'Migrated data for measurement: {measurement}')


def migrate_wifi_clients():
    client = get_influxdb_client()
    query_api = client.client.query_api()
    write_api = client.client.write_api(write_options=SYNCHRONOUS)

    read_query = 'from(bucket: "mybucket") |> range(start: -30d) |> filter(fn: (r) => r._measurement == "wifi_clients")'
    tags = {'source': 'migration'}

    migrate_influxdb_data(query_api, write_api, read_query, 'wifi_clients', tags)
    logger.info('"wifi_clients" measurements successfully migrated.')


def migrate_traffic_data():
    client = get_influxdb_client()
    query_api = client.client.query_api()
    write_api = client.client.write_api(write_options=SYNCHRONOUS)

    read_query = 'from(bucket: "mybucket") |> range(start: -30d) |> filter(fn: (r) => r._measurement == "traffic")'
    tags = {'source': 'migration'}

    migrate_influxdb_data(query_api, write_api, read_query, 'traffic', tags)
    logger.info('"traffic" measurements successfully migrated.')
