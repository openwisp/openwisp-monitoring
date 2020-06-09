import logging
from datetime import datetime

from influxdb import client

from .. import TIMESERIES_DB
from .exception import DatabaseException

logger = logging.getLogger(__name__)


class DatabaseClient(DatabaseException):
    def __init__(self):
        self._db = None
        self.db_name = None

    def create_database(self, database=TIMESERIES_DB['NAME']):
        """ creates database if necessary """
        db = self.get_db()
        # influxdb does not create a new database, neither raise an error if databese exists
        db.create_database(database)
        logger.info(f'Created influxdb database "{database}"')

    def drop_database(self, database=TIMESERIES_DB['NAME']):
        """ drops database if it exists """
        db = self.get_db()
        # influxdb does not raise an error if databese does not exist
        db.drop_database(database)
        logger.info(f'Dropped influxdb database "{database}"')

    # TODO: Needs to be improved
    def get_db(self):
        """ Returns an ``InfluxDBClient`` instance """
        if not self._db or self._db._database != self.db_name:
            self._db = client.InfluxDBClient(
                TIMESERIES_DB['HOST'],
                TIMESERIES_DB['PORT'],
                TIMESERIES_DB['USER'],
                TIMESERIES_DB['PASSWORD'],
                self.db_name or TIMESERIES_DB['NAME'],
            )
            self.db_name = self._db._database
        return self._db

    def query(self, query, **kwargs):
        db = self.get_db()
        database = kwargs.get('database') or self.db_name or TIMESERIES_DB['NAME']
        return db.query(
            query,
            kwargs.get('params'),
            epoch=kwargs.get('epoch'),
            expected_response_code=kwargs.get('expected_response_code') or 200,
            database=database,
        )

    def write(self, name, values, **kwargs):
        """ Method to be called via threading module. """
        point = {
            'measurement': name,
            'tags': kwargs.get('tags'),
            'fields': values,
        }
        timestamp = kwargs.get('timestamp')
        if isinstance(timestamp, datetime):
            timestamp = timestamp.strftime('%Y-%m-%dT%H:%M:%SZ')
        if timestamp:
            point['time'] = timestamp
        self.get_db().write(
            {'points': [point]},
            {
                'db': kwargs.get('database') or self.db_name or TIMESERIES_DB['NAME'],
                'rp': kwargs.get('retention_policy'),
            },
        )

    def read(self, key, fields, tags, **kwargs):
        """ Method to be called via threading module. """
        extra_fields = kwargs.get('extra_fields')
        since = kwargs.get('since')
        order = kwargs.get('order')
        limit = kwargs.get('limit')
        if extra_fields and extra_fields != '*':
            fields = ', '.join([fields] + extra_fields)
        elif extra_fields == '*':
            fields = '*'
        q = 'SELECT {fields} FROM {key}'.format(fields=fields, key=key)
        conditions = []
        if since:
            conditions.append("time >= {0}".format(since))
        if tags:
            conditions.append(
                ' AND '.join(["{0} = '{1}'".format(*tag) for tag in tags.items()])
            )
        if conditions:
            conditions = 'WHERE %s' % ' AND '.join(conditions)
            q = '{0} {1}'.format(q, conditions)
        if order:
            q = '{0} ORDER BY {1}'.format(q, order)
        if limit:
            q = '{0} LIMIT {1}'.format(q, limit)
        return list(self.query(q, epoch='s').get_points())
