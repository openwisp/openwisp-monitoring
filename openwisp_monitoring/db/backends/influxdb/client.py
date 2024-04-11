import logging
import operator
import re
import sys
from collections import OrderedDict
from datetime import datetime

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBClientError
from influxdb.line_protocol import make_lines

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
        return self.dbs['default']

    @cached_property
    def dbs(self):
        dbs = {
            'default': InfluxDBClient(
                TIMESERIES_DB['HOST'],
                TIMESERIES_DB['PORT'],
                TIMESERIES_DB['USER'],
                TIMESERIES_DB['PASSWORD'],
                self.db_name,
                use_udp=TIMESERIES_DB.get('OPTIONS', {}).get('udp_writes', False),
                udp_port=TIMESERIES_DB.get('OPTIONS', {}).get('udp_port', 8089),
            ),
        }
        if TIMESERIES_DB.get('OPTIONS', {}).get('udp_writes', False):
            # When using UDP, InfluxDB allows only using one retention policy
            # per port. Therefore, we need to have different instances of
            # InfluxDBClient.
            dbs['short'] = InfluxDBClient(
                TIMESERIES_DB['HOST'],
                TIMESERIES_DB['PORT'],
                TIMESERIES_DB['USER'],
                TIMESERIES_DB['PASSWORD'],
                self.db_name,
                use_udp=TIMESERIES_DB.get('OPTIONS', {}).get('udp_writes', False),
                udp_port=TIMESERIES_DB.get('OPTIONS', {}).get('udp_port', 8089) + 1,
            )
            dbs['__all__'] = InfluxDBClient(
                TIMESERIES_DB['HOST'],
                TIMESERIES_DB['PORT'],
                TIMESERIES_DB['USER'],
                TIMESERIES_DB['PASSWORD'],
                self.db_name,
            )
        else:
            dbs['short'] = dbs['default']
            dbs['__all__'] = dbs['default']
        return dbs

    @cached_property
    def use_udp(self):
        return TIMESERIES_DB.get('OPTIONS', {}).get('udp_writes', False)

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

    def _write(self, points, database, retention_policy):
        db = self.dbs['short'] if retention_policy else self.dbs['default']
        # If the size of data exceeds the limit of the UDP packet, then
        # fallback to use TCP connection for writing data.
        lines = make_lines({'points': points})
        if sys.getsizeof(lines) > 65000:
            db = self.dbs['__all__']
        try:
            db.write_points(
                points=lines.split('\n')[:-1],
                database=database,
                retention_policy=retention_policy,
                protocol='line',
            )
        except Exception as exception:
            logger.warning(f'got exception while writing to tsdb: {exception}')
            if isinstance(exception, self.client_error):
                exception_code = getattr(exception, 'code', None)
                # do not retry any request which returns 400
                if exception_code == 400:
                    return
            raise TimeseriesWriteException

    def _get_timestamp(self, timestamp=None):
        timestamp = timestamp or now()
        if isinstance(timestamp, datetime):
            return timestamp.isoformat(sep='T', timespec='microseconds')
        return timestamp

    def write(self, name, values, **kwargs):
        timestamp = self._get_timestamp(timestamp=kwargs.get('timestamp'))
        point = {
            'measurement': name,
            'tags': kwargs.get('tags'),
            'fields': values,
            'time': timestamp,
        }
        self._write(
            points=[point],
            database=kwargs.get('database') or self.db_name,
            retention_policy=kwargs.get('retention_policy'),
        )

    def batch_write(self, metric_data):
        data_points = {}
        for data in metric_data:
            org = data.get('database') or self.db_name
            retention_policy = data.get('retention_policy')
            if org not in data_points:
                data_points[org] = {}
            if retention_policy not in data_points[org]:
                data_points[org][retention_policy] = []
            timestamp = self._get_timestamp(timestamp=data.get('timestamp'))
            data_points[org][retention_policy].append(
                {
                    'measurement': data.get('name'),
                    'tags': data.get('tags'),
                    'fields': data.get('values'),
                    'time': timestamp,
                }
            )
        for database in data_points.keys():
            for rp in data_points[database].keys():
                self._write(
                    points=data_points[database][rp],
                    database=database,
                    retention_policy=rp,
                )

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
        result = self.query(query, precision=precision)
        if not len(result.keys()) or result.keys()[0][1] is None:
            return list(result.get_points())
        # Handles query which contains "GROUP BY TAG" clause
        result_points = {}
        for (measurement, tag), group_points in result.items():
            tag_suffix = '_'.join(tag.values())
            for point in group_points:
                values = {}
                for key, value in point.items():
                    if key != 'time':
                        values[tag_suffix] = value
                values['time'] = point['time']
                try:
                    result_points[values['time']].update(values)
                except KeyError:
                    result_points[values['time']] = values
        return list(result_points.values())

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

    def _clean_params(self, params):
        if params.get('end_date'):
            params['end_date'] = f'AND time <= \'{params["end_date"]}\''
        else:
            params['end_date'] = ''
        for key, value in params.items():
            if isinstance(value, list) or isinstance(value, tuple):
                params[key] = self._get_where_query(key, value)
        return params

    def _get_where_query(self, field, items):
        if not items:
            return ''
        lookup = []
        for item in items:
            lookup.append(f"{field} = '{item}'")
        return 'AND ({lookup})'.format(lookup=' OR '.join(lookup))

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
        params = self._clean_params(params)
        query = query.format(**params)
        query = self._group_by(query, time, chart_type, group_map, strip=summary)
        if summary:
            query = f'{query} LIMIT 1'
        return f"{query} tz('{timezone}')"

    _group_by_time_tag_regex = re.compile(
        r'GROUP BY ((time\(\w+\))(?:,\s+\w+)?)', flags=re.IGNORECASE
    )
    _group_by_time_regex = re.compile(r'GROUP BY time\(\w+\)\s?', flags=re.IGNORECASE)
    _time_regex = re.compile(r'time\(\w+\)\s?', flags=re.IGNORECASE)
    _time_comma_regex = re.compile(r'time\(\w+\),\s?', flags=re.IGNORECASE)

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
            # The query could have GROUP BY clause for a TAG
            if group_by:
                # The query already contains "GROUP BY", therefore
                # we remove it from the "group_by" to avoid duplicating
                # "GROUP BY"
                group_by = group_by.replace('GROUP BY ', '')
                # We only need to substitute the time function.
                # The resulting query would be "GROUP BY time(<group_by>), <tag>"
                query = re.sub(self._time_regex, group_by, query)
            else:
                # The query should not include the "GROUP by time()"
                matches = re.search(self._group_by_time_tag_regex, query)
                group_by_fields = matches.group(1)
                if len(group_by_fields.split(',')) > 1:
                    # If the query has "GROUP BY time(), tag",
                    # then return "GROUP BY tag"
                    query = re.sub(self._time_comma_regex, '', query)
                else:
                    # If the query has only has "GROUP BY time()",
                    # then remove the "GROUP BY" clause
                    query = re.sub(self._group_by_time_regex, '', query)
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
