import logging
import re
from datetime import datetime

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

from ...exceptions import TimeseriesWriteException

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

    def __init__(self, bucket, org, token, url):
        self.bucket = bucket
        self.org = org
        self.token = token
        self.url = url
        self.client = InfluxDBClient(url=url, token=token, org=org)
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
        self.query_api = self.client.query_api()

    def create_database(self):
        logger.debug('InfluxDB 2.0 does not require explicit database creation.')

    def drop_database(self):
        logger.debug('InfluxDB 2.0 does not support dropping databases via the client.')

    def create_or_alter_retention_policy(self, name, duration):
        logger.debug('InfluxDB 2.0 handles retention policies via bucket settings.')

    def write(self, name, values, **kwargs):
        timestamp = kwargs.get('timestamp', datetime.utcnow().isoformat())
        point = (
            Point(name)
            .tag("object_id", kwargs.get('tags').get('object_id'))
            .field(kwargs.get('field'), values)
            .time(timestamp)
        )
        try:
            self.write_api.write(bucket=self.bucket, org=self.org, record=point)
        except Exception as exception:
            logger.warning(f'got exception while writing to tsdb: {exception}')
            raise TimeseriesWriteException

    def batch_write(self, metric_data):
        points = []
        for data in metric_data:
            timestamp = data.get('timestamp', datetime.utcnow().isoformat())
            point = (
                Point(data.get('name'))
                .tag("object_id", data.get('tags').get('object_id'))
                .field(data.get('field'), data.get('values'))
                .time(timestamp)
            )
            points.append(point)
        try:
            self.write_api.write(bucket=self.bucket, org=self.org, record=points)
        except Exception as exception:
            logger.warning(f'got exception while writing to tsdb: {exception}')
            raise TimeseriesWriteException

    def read(self, key, fields, tags=None, **kwargs):
        since = kwargs.get('since')
        order = kwargs.get('order')
        limit = kwargs.get('limit')
        query = (
            f'from(bucket: "{self.bucket}")'
            f' |> range(start: {since if since else "-1h"})'  # Use since or default
            f' |> filter(fn: (r) => r._measurement == "{key}")'
        )
        if tags:
            tag_query = ' and '.join(
                [f'r.{tag} == "{value}"' for tag, value in tags.items()]
            )
            query += f' |> filter(fn: (r) => {tag_query})'
        if fields:
            field_query = ' or '.join([f'r._field == "{field}"' for field in fields])
            query += f' |> filter(fn: (r) => {field_query})'
        if order:
            query += f' |> sort(columns: ["_time"], desc: {order == "-time"})'
        if limit:
            query += f' |> limit(n: {limit})'
        result = self.query_api.query(org=self.org, query=query)
        return [record.values for table in result for record in table.records]

    def delete_metric_data(self, key=None, tags=None):
        logger.debug(
            'InfluxDB 2.0 does not support deleting specific data points via the client.'
        )

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
        params = self._clean_params(params)
        query = query.format(**params)
        query = self._group_by(query, time, chart_type, group_map, strip=summary)
        if summary:
            query = f'{query} |> limit(n: 1)'
        return query

    def _fields(self, fields, query, field_name):
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

    def _group_by(self, query, time, chart_type, group_map, strip=False):
        if not self.validate_query(query):
            return query
        if not strip and not chart_type == 'histogram':
            value = group_map[time]
            group_by = (
                f'|> aggregateWindow(every: {value}, fn: mean, createEmpty: false)'
            )
        else:
            group_by = ''
        if 'aggregateWindow' not in query:
            query = f'{query} {group_by}'
        return query


# Example usage
if __name__ == "__main__":
    bucket = "mybucket"
    org = "myorg"
    token = "t8Q3Y5mTWuqqTRdGyVxZuyVLO-8pl3I8KaNTR3jV7uTDr_GVECP5Z7LsrZwILGw79Xp4O8pAWkdqTREgIk073Q=="
    url = "http://localhost:9086"

    client = DatabaseClient(bucket=bucket, org=org, token=token, url=url)
    client.create_database()

    # Write example
    client.write(
        "example_measurement", 99.5, tags={"object_id": "server_01"}, field="uptime"
    )

    # Read example
    result = client.read(
        "example_measurement", ["uptime"], tags={"object_id": "server_01"}
    )
    print(result)
