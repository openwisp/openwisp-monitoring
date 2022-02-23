import logging
import operator
import re
from collections import OrderedDict
from datetime import datetime

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBClientError

from openwisp_monitoring.utils import retry

from ...exceptions import TimeseriesWriteException
from .. import TIMESERIES_DB

logger = logging.getLogger(__name__)


class DatabaseClient(object):
    _AGGREGATE = [
        'COUNT',
        'DISTINCT',
        'INTEGRAL',
        'MEAN',
        'MEDIAN',
        'MODE',
        'SPREAD',
        'STDDEV',
        'SUM',
        'BOTTOM',
        'FIRST',
        'LAST',
        'MAX',
        'MIN',
        'PERCENTILE',
        'SAMPLE',
        'TOP',
        'CEILING',
        'CUMULATIVE_SUM',
        'DERIVATIVE',
        'DIFFERENCE',
        'ELAPSED',
        'FLOOR',
        'HISTOGRAM',
        'MOVING_AVERAGE',
        'NON_NEGATIVE_DERIVATIVE',
        'HOLT_WINTERS',
    ]
    _FORBIDDEN = ['drop', 'create', 'delete', 'alter', 'into']
    backend_name = 'influxdb'

    def __init__(self, db_name=None):
        self._db = None
        self.db_name = db_name or TIMESERIES_DB['NAME']
        self.client_error = InfluxDBClientError

    @retry
    def create_database(self):
        """creates database if necessary"""
        # InfluxDB does not create a new database, neither raise an error if database exists
        self.db.create_database(self.db_name)
        logger.debug(f'Created InfluxDB database "{self.db_name}"')

    @retry
    def drop_database(self):
        """drops database if it exists"""
        # InfluxDB does not raise an error if database does not exist
        self.db.drop_database(self.db_name)
        logger.debug(f'Dropped InfluxDB database "{self.db_name}"')

    @cached_property
    def db(self):
        """Returns an ``InfluxDBClient`` instance"""
        return InfluxDBClient(
            TIMESERIES_DB['HOST'],
            TIMESERIES_DB['PORT'],
            TIMESERIES_DB['USER'],
            TIMESERIES_DB['PASSWORD'],
            self.db_name,
        )

    @retry
    def create_or_alter_retention_policy(self, name, duration):
        """creates or alters existing retention policy if necessary"""
        retention_policies = self.db.get_list_retention_policies()
        exists = False
        duration_changed = False
        for policy in retention_policies:
            if policy['name'] == name:
                exists = True
                duration_changed = policy['duration']
                break
        if not exists:
            self.db.create_retention_policy(name=name, duration=duration, replication=1)
        elif exists and duration_changed:
            self.db.alter_retention_policy(name=name, duration=duration)

    @retry
    def query(self, query, precision=None, **kwargs):
        database = kwargs.get('database') or self.db_name
        return self.db.query(
            query,
            kwargs.get('params'),
            epoch=precision,
            expected_response_code=kwargs.get('expected_response_code') or 200,
            database=database,
        )

    def write(self, name, values, **kwargs):
        point = {'measurement': name, 'tags': kwargs.get('tags'), 'fields': values}
        timestamp = kwargs.get('timestamp') or now()
        if isinstance(timestamp, datetime):
            timestamp = timestamp.isoformat(sep='T', timespec='microseconds')
        point['time'] = timestamp
        try:
            self.db.write(
                {'points': [point]},
                {
                    'db': kwargs.get('database') or self.db_name,
                    'rp': kwargs.get('retention_policy'),
                },
            )
        except Exception as exception:
            logger.warning(f'got exception while writing to tsdb: {exception}')
            if isinstance(exception, self.client_error):
                exception_code = getattr(exception, 'code', None)
                exception_message = getattr(exception, 'content')
                if (
                    exception_code == 400
                    and 'points beyond retention policy dropped' in exception_message
                ):
                    return
            raise TimeseriesWriteException

    def read(self, key, fields, tags, **kwargs):
        extra_fields = kwargs.get('extra_fields')
        since = kwargs.get('since')
        order = kwargs.get('order')
        limit = kwargs.get('limit')
        rp = kwargs.get('retention_policy')
        if extra_fields and extra_fields != '*':
            fields = ', '.join([fields] + extra_fields)
        elif extra_fields == '*':
            fields = '*'
        from_clause = f'{rp}.{key}' if rp else key
        q = f'SELECT {fields} FROM {from_clause}'
        conditions = []
        if since:
            conditions.append(f'time >= {since}')
        if tags:
            conditions.append(
                ' AND '.join(["{0} = '{1}'".format(*tag) for tag in tags.items()])
            )
        if conditions:
            conditions = 'WHERE %s' % ' AND '.join(conditions)
            q = f'{q} {conditions}'
        if order:
            # InfluxDB only allows ordering results by time
            if order == 'time':
                order = 'time ASC'
            elif order == '-time':
                order = 'time DESC'
            else:
                raise self.client_error(
                    f'Invalid order "{order}" passed.\nYou may pass "time" / "-time" to get '
                    'result sorted in ascending /descending order respectively.'
                )
            q = f'{q} ORDER BY {order}'
        if limit:
            q = f'{q} LIMIT {limit}'
        return list(self.query(q, precision='s').get_points())

    def get_list_query(self, query, precision='s'):
        return list(self.query(query, precision=precision).get_points())

    @retry
    def get_list_retention_policies(self):
        return self.db.get_list_retention_policies()

    def delete_metric_data(self, key=None, tags=None):
        """
        deletes a specific metric based on the key and tags
        provided, you may also choose to delete all metrics
        """
        if not key and not tags:
            self.query('DROP SERIES FROM /.*/')
        else:
            self.delete_series(key, tags)

    @retry
    def delete_series(self, key=None, tags=None):
        self.db.delete_series(measurement=key, tags=tags)

    # Chart related functions below

    def validate_query(self, query):
        for word in self._FORBIDDEN:
            if word in query.lower():
                msg = _(f'the word "{word.upper()}" is not allowed')
                raise ValidationError({'configuration': msg})
        return self._is_aggregate(query)

    def _is_aggregate(self, q):
        q = q.upper()
        for word in self._AGGREGATE:
            if any(['%s(' % word in q, '|%s}' % word in q, '|%s|' % word in q]):
                return True
        return False

    def get_query(
        self,
        chart_type,
        params,
        time,
        group_map,
        summary=False,
        fields=None,
        query=None,
        timezone=settings.TIME_ZONE,
    ):
        query = self._fields(fields, query, params['field_name'])
        query = query.format(**params)
        query = self._group_by(query, time, chart_type, group_map, strip=summary)
        if summary:
            query = f'{query} LIMIT 1'
        return f"{query} tz('{timezone}')"

    _group_by_regex = re.compile(r'GROUP BY time\(\w+\)', flags=re.IGNORECASE)

    def _group_by(self, query, time, chart_type, group_map, strip=False):
        if not self.validate_query(query):
            return query
        if not strip and not chart_type == 'histogram':
            value = group_map[time]
            group_by = f'GROUP BY time({value})'
        else:
            # can be empty when getting summaries
            group_by = ''
        if 'GROUP BY' not in query.upper():
            query = f'{query} {group_by}'
        else:
            query = re.sub(self._group_by_regex, group_by, query)
        return query

    _fields_regex = re.compile(
        r'(?P<group>\{fields\|(?P<func>\w+)(?:\|(?P<op>.*?))?\})', flags=re.IGNORECASE
    )

    def _fields(self, fields, query, field_name):
        """
        support substitution of {fields|<FUNCTION_NAME>|<OPERATION>}
        with <FUNCTION_NAME>(field1) AS field1 <OPERATION>,
             <FUNCTION_NAME>(field2) AS field2 <OPERATION>
        """
        matches = re.search(self._fields_regex, query)
        if not matches and not fields:
            return query
        elif matches and not fields:
            groups = matches.groupdict()
            fields_key = groups.get('group')
            fields = [field_name]
        if fields and matches:
            groups = matches.groupdict()
            function = groups['func']  # required
            operation = groups.get('op')  # optional
            fields = [self.__transform_field(f, function, operation) for f in fields]
            fields_key = groups.get('group')
        else:
            fields_key = '{fields}'
        if fields:
            selected_fields = ', '.join(fields)
        return query.replace(fields_key, selected_fields)

    def __transform_field(self, field, function, operation=None):
        if operation:
            operation = f' {operation}'
        else:
            operation = ''
        return f'{function}("{field}"){operation} AS {field.replace("-", "_")}'

    def _get_top_fields(
        self,
        query,
        params,
        chart_type,
        group_map,
        number,
        time,
        timezone=settings.TIME_ZONE,
    ):
        q = self.get_query(
            query=query,
            params=params,
            chart_type=chart_type,
            group_map=group_map,
            summary=True,
            fields=['SUM(*)'],
            time=time,
            timezone=timezone,
        )
        res = list(self.query(q, precision='s').get_points())
        if not res:
            return []
        res = res[0]
        res = {key: value for key, value in res.items() if value is not None}
        sorted_dict = OrderedDict(sorted(res.items(), key=operator.itemgetter(1)))
        del sorted_dict['time']
        keys = list(sorted_dict.keys())
        keys.reverse()
        top = keys[0:number]
        return [item.replace('sum_', '') for item in top]
