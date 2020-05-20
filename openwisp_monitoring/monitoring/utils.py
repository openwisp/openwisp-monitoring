import logging
from datetime import datetime

from influxdb import client

from . import settings

logger = logging.getLogger(__name__)


def get_db():
    """ Returns an ``InfluxDBClient`` instance """
    return client.InfluxDBClient(
        settings.INFLUXDB_HOST,
        settings.INFLUXDB_PORT,
        settings.INFLUXDB_USER,
        settings.INFLUXDB_PASSWORD,
        settings.INFLUXDB_DATABASE,
    )


def query(query, params=None, epoch=None, expected_response_code=200, database=None):
    """ Wrapper around ``InfluxDBClient.query()`` """
    db = get_db()
    database = database or settings.INFLUXDB_DATABASE
    return db.query(
        query,
        params,
        epoch=epoch,
        expected_response_code=expected_response_code,
        database=database,
    )


def write(
    name, values, tags=None, timestamp=None, database=None, retention_policy=None
):
    """ Method to be called via threading module. """
    point = {'measurement': name, 'tags': tags, 'fields': values}
    if isinstance(timestamp, datetime):
        timestamp = timestamp.strftime('%Y-%m-%dT%H:%M:%SZ')
    if timestamp:
        point['time'] = timestamp
    try:
        get_db().write(
            {'points': [point]},
            {'db': database or settings.INFLUXDB_DATABASE, 'rp': retention_policy},
        )
    except Exception as e:
        raise e


def create_database():
    """ creates database if necessary """
    db = get_db()
    response = db.query('SHOW DATABASES')
    items = list(response.get_points('databases'))
    databases = [database['name'] for database in items]
    # if database does not exists, create it
    if settings.INFLUXDB_DATABASE not in databases:
        db.create_database(settings.INFLUXDB_DATABASE)
        logger.info(f'Created influxdb database {settings.INFLUXDB_DATABASE}')
