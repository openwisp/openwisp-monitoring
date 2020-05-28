from datetime import datetime

from influxdb import client

from .. import TIMESERIES_DB
from .creation import DatabaseCreation
from .exception import DatabaseException


class DatabaseClient(DatabaseCreation, DatabaseException):
    def get_db(self):
        """ Returns an ``InfluxDBClient`` instance """
        return client.InfluxDBClient(
            TIMESERIES_DB['HOST'],
            TIMESERIES_DB['PORT'],
            TIMESERIES_DB['USER'],
            TIMESERIES_DB['PASSWORD'],
            TIMESERIES_DB['NAME'],
        )

    def query(self, query, **kwargs):
        db = self.get_db()
        database = kwargs.get('database') or TIMESERIES_DB['NAME']
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
        try:
            self.get_db().write(
                {'points': [point]},
                {
                    'db': kwargs.get('database') or TIMESERIES_DB['NAME'],
                    'rp': kwargs.get('retention_policy'),
                },
            )
        except Exception as e:
            raise e

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
