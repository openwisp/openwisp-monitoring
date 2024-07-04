from datetime import datetime, time, timezone
from django.conf import settings
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
import re
import pytz
from django.utils.timezone import now
import logging
from .. import TIMESERIES_DB
from django.core.exceptions import ValidationError
from influxdb_client.rest import ApiException as InfluxDBClientError
from django.utils.translation import gettext_lazy as _
from django.utils.dateparse import parse_datetime


logger = logging.getLogger(__name__)

class DatabaseClient:
    _AGGREGATE = [
        'COUNT', 'DISTINCT', 'INTEGRAL', 'MEAN', 'MEDIAN', 'MODE',
        'SPREAD', 'STDDEV', 'SUM', 'BOTTOM', 'FIRST', 'LAST',
        'MAX', 'MIN', 'PERCENTILE', 'SAMPLE', 'TOP', 'CEILING',
        'CUMULATIVE_SUM', 'DERIVATIVE', 'DIFFERENCE', 'ELAPSED',
        'FLOOR', 'HISTOGRAM', 'MOVING_AVERAGE', 'NON_NEGATIVE_DERIVATIVE',
        'HOLT_WINTERS'
    ]
    _FORBIDDEN = ['drop', 'delete', 'alter', 'into']
    backend_name = 'influxdb2'

    def __init__(self, bucket=None, org=None, token=None, url=None):
        self.bucket = bucket or TIMESERIES_DB['BUCKET']
        self.org = org or TIMESERIES_DB['ORG']
        self.token = token or TIMESERIES_DB['TOKEN']
        self.url = url or f'http://{TIMESERIES_DB["HOST"]}:{TIMESERIES_DB["PORT"]}'
        self.client = InfluxDBClient(url=self.url, token=self.token, org=self.org)
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
        self.query_api = self.client.query_api()
        self.forbidden_pattern = re.compile(
            r'\b(' + '|'.join(self._FORBIDDEN) + r')\b', re.IGNORECASE
        )
        self.client_error = InfluxDBClientError

    def create_database(self):
        logger.debug('InfluxDB 2.0 does not require explicit database creation.')
        # self.create_bucket(self.bucket)

    def drop_database(self):
        logger.debug('InfluxDB 2.0 does not support dropping databases via the client.')

    def create_or_alter_retention_policy(self, name, duration):
        logger.debug('InfluxDB 2.0 handles retention policies via bucket settings.')

    def create_bucket(self, bucket, retention_rules=None):
        bucket_api = self.client.buckets_api()
        try:
            existing_bucket = bucket_api.find_bucket_by_name(bucket)
            if existing_bucket:
                logger.info(f'Bucket "{bucket}" already exists.')
                return
        except Exception as e:
            logger.error(f"Error checking for existing bucket: {e}")

        try:
            bucket_api.create_bucket(bucket_name=bucket, retention_rules=retention_rules, org=self.org)
            logger.info(f'Created bucket "{bucket}"')
        except self.client_error as e:
            if "already exists" in str(e):
                logger.info(f'Bucket "{bucket}" already exists.')
            else:
                logger.error(f"Error creating bucket: {e}")
                raise

    def drop_bucket(self):
        bucket_api = self.client.buckets_api()
        bucket = bucket_api.find_bucket_by_name(self.bucket)
        if bucket:
            bucket_api.delete_bucket(bucket.id)
            logger.debug(f'Dropped InfluxDB bucket "{self.bucket}"')

    def _get_timestamp(self, timestamp=None):
        timestamp = timestamp or now()
        if isinstance(timestamp, datetime):
            return timestamp.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        return timestamp

    def write(self, name, values, **kwargs):
        timestamp = self._get_timestamp(timestamp=kwargs.get('timestamp'))
        try:   
            point = {
                'measurement': name,
                'tags': kwargs.get('tags'),
                'fields': values,
                'time': timestamp,
            }
            print(f"Writing point to InfluxDB: {point}")
            self.write_api.write(bucket=self.bucket, org=self.org, record=point)
            print("Successfully wrote point to InfluxDB")
        except Exception as e:
            print(f"Error writing to InfluxDB: {e}")

    def batch_write(self, metric_data):
        points = []
        for data in metric_data:
            timestamp = self._get_timestamp(timestamp=data.get('timestamp'))
            point = Point(data.get('name')).tag(**data.get('tags', {})).field(**data.get('values')).time(timestamp, WritePrecision.NS)
            points.append(point)   
        try:
            self.write_api.write(bucket=self.bucket, org=self.org, record=points)
        except Exception as e:
            logger.error(f"Error writing batch to InfluxDB: {e}")

    def _format_date(self, date_str):
        if date_str is None or date_str == 'now()':
            return date_str
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
            return date.strftime('%Y-%m-%dT%H:%M:%SZ')
        except ValueError:
            # If the date_str is not in the expected format, return it as is
            return date_str
        
    def query(self, query):
        print(f"Executing query: {query}")
        try:
            result = self.query_api.query(query)
            print(f"Query result: {result}")
            return result
        except Exception as e:
            print(f"Error executing query: {e}")
            logger.error(f"Error executing query: {e}")
            return []
        
    def _parse_query_result(self, result):
        print("Parsing query result")
        parsed_result = []
        for table in result:
            for record in table.records:
                parsed_record = {
                    'time': record.get_time().isoformat(),
                }
                for key, value in record.values.items():
                    if key not in ['_time', '_start', '_stop', '_measurement']:
                        parsed_record[key] = value
                parsed_result.append(parsed_record)
        print(f"Parsed result: {parsed_result}")
        return parsed_result
 
    def read(self, key, fields, tags, **kwargs):
        extra_fields = kwargs.get('extra_fields')
        since = kwargs.get('since', '-30d')  # Default to last 30 days if not specified
        order = kwargs.get('order')
        limit = kwargs.get('limit')
        bucket = self.bucket

        # Start building the Flux query
        flux_query = f'from(bucket:"{bucket}")'

        # Add time range
        flux_query += f'\n  |> range(start: {since})'

        # Filter by measurement (key)
        flux_query += f'\n  |> filter(fn: (r) => r["_measurement"] == "{key}")'

        # Filter by fields
        if fields != '*':
            if extra_fields and extra_fields != '*':
                all_fields = [fields] + extra_fields if isinstance(extra_fields, list) else [fields, extra_fields]
                field_filter = ' or '.join([f'r["_field"] == "{field}"' for field in all_fields])
            else:
                field_filter = f'r["_field"] == "{fields}"'
            flux_query += f'\n  |> filter(fn: (r) => {field_filter})'

        # Filter by tags
        if tags:
            tag_filters = ' and '.join([f'r["{tag}"] == "{value}"' for tag, value in tags.items()])
            flux_query += f'\n  |> filter(fn: (r) => {tag_filters})'

        # Add ordering
        if order:
            if order in ['time', '-time']:
                desc = 'true' if order == '-time' else 'false'
                flux_query += f'\n  |> sort(columns: ["_time"], desc: {desc})'
            else:
                raise self.client_error(
                    f'Invalid order "{order}" passed.\nYou may pass "time" / "-time" to get '
                    'result sorted in ascending /descending order respectively.'
                )

        # Add limit
        if limit:
            flux_query += f'\n  |> limit(n: {limit})'

        # Pivot the result to make it similar to InfluxDB 1.x output
        flux_query += '\n  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")'

        # Execute the query
        try:
            result = self.query_api.query(flux_query)
            return self._parse_read_result(result)
        except Exception as e:
            logger.error(f"Error executing read query: {e}")
            return []

    def _parse_read_result(self, result):
        parsed_result = []
        for table in result:
            for record in table.records:
                parsed_record = {
                    'time': record.get_time().isoformat(),
                }
                for key, value in record.values.items():
                    if key not in ['_time', '_start', '_stop', '_measurement']:
                        parsed_record[key] = value
                parsed_result.append(parsed_record)
        return parsed_result

    def execute_query(self, query):
        try:
            result = self.query_api.query(query)
            return self._parse_result(result)
        except Exception as e:
            logger.error(f"Error executing query: {e}")
            return []

    def _parse_result(self, result):
        parsed_result = []
        for table in result:
            for record in table.records:
                parsed_record = {
                    'time': record.get_time().isoformat(),
                    'device_id': record.values.get('object_id'),
                    'field': record.values.get('_field'),
                    'value': record.values.get('_value')
                }
                parsed_result.append(parsed_record)
        return parsed_result
    
    def delete_metric_data(self, key=None, tags=None):
        start = "1970-01-01T00:00:00Z"
        stop = "2100-01-01T00:00:00Z"
        predicate = ""
        if key:
            predicate += f'r._measurement == "{key}"'
        if tags:
            tag_filters = ' and '.join([f'r["{tag}"] == "{value}"' for tag, value in tags.items()])
            if predicate:
                predicate += f' and {tag_filters}'
            else:
                predicate = tag_filters
        self.client.delete_api().delete(start, stop, predicate, bucket=self.bucket, org=self.org)

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
            params['end_date'] = f"stop: {params['end_date']}"
        else:
            params['end_date'] = ''
    
        for key, value in params.items():
            if isinstance(value, (list, tuple)):
                params[key] = self._get_filter_query(key, value)
    
        return params

    def _get_filter_query(self, field, items):
        if not items:
            return ''
        filters = []
        for item in items:
            filters.append(f'r["{field}"] == "{item}"')
        return f'|> filter(fn: (r) => {" or ".join(filters)})'

    def get_query(
        self,
        chart_type,
        params,
        time,
        group_map,
        summary=False,
        fields=None,
        query=None,
        timezone=settings.TIME_ZONE
    ):
        bucket = self.bucket
        measurement = params.get('key')
        if not measurement or measurement == 'None':
            logger.error("Invalid or missing measurement in params")
            return None

        start_date = params.get('start_date')
        end_date = params.get('end_date')
        
        # Set default values for start and end dates if they're None
        if start_date is None:
            start_date = f'-{time}'
        if end_date is None:
            end_date = 'now()'

        content_type = params.get('content_type')
        object_id = params.get('object_id')
        field_name = params.get('field_name') or fields

        object_id_filter = f' and r.object_id == "{object_id}"' if object_id else ""

        flux_query = f'''
        from(bucket: "{bucket}")
            |> range(start: {start_date}, stop: {end_date})
            |> filter(fn: (r) => r._measurement == "{measurement}")
            |> filter(fn: (r) => r.content_type == "{content_type}"{object_id_filter})
        '''

        if field_name:
            if isinstance(field_name, (list, tuple)):
                field_filter = ' or '.join([f'r._field == "{field}"' for field in field_name])
            else:
                field_filter = f'r._field == "{field_name}"'
            flux_query += f'    |> filter(fn: (r) => {field_filter})\n'

        logger.debug(f"Time: {time}")
        logger.debug(f"Group map: {group_map}")
        window = group_map.get(time, '1h')
        logger.debug(f"Window: {window}")

        if not summary:
            flux_query += f'    |> aggregateWindow(every: {window}, fn: mean, createEmpty: false)\n'
        else:
            flux_query += '    |> last()\n'

        flux_query += '    |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")\n'
        flux_query += '    |> yield(name: "result")'

        logger.debug(f"Generated Flux query: {flux_query}")
        return flux_query
    
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
            function = groups['func']
            operation = groups.get('op')
            fields = [self.__transform_field(f, function, operation) for f in fields]
            fields_key = groups.get('group')
        else:
            fields_key = '{fields}'
        if fields:
            selected_fields = ', '.join(fields)
        return query.replace(fields_key, selected_fields)

    def __transform_field(self, field, function, operation=None):
        if operation:
            operation = f' |> {operation}'
        else:
            operation = ''
        return f'{function}(r.{field}){operation} |> rename(columns: {{_{field}: "{field}"}})'

    def _get_top_fields(self, query, params, chart_type, group_map, number, time, timezone=settings.TIME_ZONE):
        q = self.get_query(query=query, params=params, chart_type=chart_type, group_map=group_map, summary=True, fields=['SUM(*)'], time=time, timezone=timezone)
        flux_query = f'''
            {q}
            |> aggregateWindow(every: {time}, fn: sum, createEmpty: false)
            |> group(columns: ["_field"])
            |> sum()
            |> sort(columns: ["_value"], desc: true)
            |> limit(n: {number})
            |> map(fn: (r) => ({{ r with _field: r._field }}))
        '''
        result = list(self.query_api.query(flux_query))
        top_fields = [record["_field"] for table in result for record in table.records]
        return top_fields

    def default_chart_query(self, tags):
        q = f'''
        from(bucket: "{self.bucket}")
          |> range(start: {{time}})
          |> filter(fn: (r) => r._measurement == "{{key}}")
          |> filter(fn: (r) => r._field == "{{field_name}}")
        '''
        if tags:
            q += '''
          |> filter(fn: (r) => r.content_type == "{{content_type}}")
          |> filter(fn: (r) => r.object_id == "{{object_id}}")
            '''
        if '{{end_date}}' in tags:
            q += '  |> range(stop: {{end_date}})'
        return q

    def _device_data(self, key, tags, rp, **kwargs):
        """ returns last snapshot of ``device_data`` """
        query = f'''
        from(bucket: "{self.bucket}")
          |> range(start: -30d)
          |> filter(fn: (r) => r._measurement == "ping")
          |> filter(fn: (r) => r.pk == "{tags['pk']}")
          |> last()
          |> yield(name: "last")
        '''
        print(f"Modified _device_data query: {query}")
        return self.get_list_query(query, precision=None)

    def get_list_query(self, query, precision='s', **kwargs):
        print(f"get_list_query called with query: {query}")
        result = self.query(query)
        parsed_result = self._parse_query_result(result) if result else []
        print(f"get_list_query result: {parsed_result}")
        return parsed_result
    
    def get_device_data_structure(self, device_pk):
        query = f'''
        from(bucket: "{self.bucket}")
        |> range(start: -30d)
        |> filter(fn: (r) => r._measurement == "ping")
        |> filter(fn: (r) => r.pk == "{device_pk}")
        |> limit(n: 1)
        '''
        print(f"Checking device data structure: {query}")
        result = self.query(query)
        if result:
            for table in result:
                for record in table.records:
                    print(f"Sample record: {record}")
                    print(f"Available fields: {record.values.keys()}")
        else:
            print("No data found for this device")
        
    def close(self):
        self.client.close()

#todo
# bucket_api.find_bucket_by_name("openwisp")
