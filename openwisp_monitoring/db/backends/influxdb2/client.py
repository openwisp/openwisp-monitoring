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
            self.write_api.write(bucket=self.bucket, org=self.org, record=point)
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
        
    def get_query(self, chart_type, params, time, group_map, summary=False, fields=None, query=None, timezone=settings.TIME_ZONE):
        print(f"get_query called with params: {params}")
        measurement = params.get('measurement') or params.get('key')
        if not measurement or measurement == 'None':
            logger.error(f"Invalid or missing measurement in params: {params}")
            return None

        start_date = self._format_date(params.get('start_date', f'-{time}'))
        end_date = self._format_date(params.get('end_date', 'now()'))
        content_type = params.get('content_type')
        object_id = params.get('object_id')


        window = group_map.get(time, '1h')

        flux_query = f'''
        from(bucket: "{self.bucket}")
          |> range(start: {start_date}, stop: {end_date})
          |> filter(fn: (r) => r["_measurement"] == "{measurement}")
        '''

        if content_type and object_id:
            flux_query += f'  |> filter(fn: (r) => r.content_type == "{content_type}" and r.object_id == "{object_id}")\n'

        if fields:
            field_filters = ' or '.join([f'r["_field"] == "{field}"' for field in fields])
            flux_query += f'  |> filter(fn: (r) => {field_filters})\n'

        flux_query += f'  |> aggregateWindow(every: {window}, fn: mean, createEmpty: false)\n'
        flux_query += '  |> yield(name: "mean")'

        print(f"Generated Flux query: {flux_query}")
        return flux_query

    def query(self, query):
        print(f"Executing query: {query}")
        try:
            result = self.query_api.query(query)
            return result
        except Exception as e:
            logger.error(f"Error executing query: {e}")

    def read(self, measurement, fields, tags, **kwargs):
        extra_fields = kwargs.get('extra_fields')
        since = kwargs.get('since', '-30d')
        order = kwargs.get('order')
        limit = kwargs.get('limit')

        flux_query = f'''
        from(bucket: "{self.bucket}")
            |> range(start: {since})
            |> filter(fn: (r) => r._measurement == "{measurement}")
        '''
        if fields and fields != '*':
            field_filters = ' or '.join([f'r._field == "{field}"' for field in fields.split(', ')])
            flux_query += f' |> filter(fn: (r) => {field_filters})'
    
        if tags:
            tag_filters = ' and '.join([f'r["{tag}"] == "{value}"' for tag, value in tags.items()])
            flux_query += f' |> filter(fn: (r) => {tag_filters})'

        flux_query += '''
            |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
            |> map(fn: (r) => ({r with _value: float(v: r._value)}))
            |> keep(columns: ["_time", "_value", "_field", "content_type", "object_id"])
            |> rename(columns: {_time: "time"})
        '''

        if order:
            if order == 'time':
                flux_query += ' |> sort(columns: ["time"], desc: false)'
            elif order == '-time':
                flux_query += ' |> sort(columns: ["time"], desc: true)'
            else:
                raise ValueError(f'Invalid order "{order}" passed.\nYou may pass "time" / "-time" to get result sorted in ascending /descending order respectively.')
    
        if limit:
            flux_query += f' |> limit(n: {limit})'

        return self.query(flux_query)

    def get_list_query(self, query, precision=None):
        print(f"get_list_query called with query: {query}")
        result = self.query(query)
        result_points = []
    
        if result is None:
            print("Query returned None")
            return result_points

        for table in result:
            for record in table.records:
                time = record.get_time()
                if precision is not None:
                    # Truncate the time based on the specified precision
                    time = time.isoformat()[:precision]
                else:
                    time = time.isoformat()
            
                values = {col: record.values.get(col) for col in record.values if col != '_time'}
                values['time'] = time
                values['_value'] = record.get_value()
                values['_field'] = record.get_field()            
                result_points.append(values)
    
        print(f"get_list_query returned {len(result_points)} points")
        print(f"Processed result points: {result_points}")
        return result_points
    
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

    # def get_query(self, chart_type, params, time, group_map, summary=False, fields=None, query=None, timezone=settings.TIME_ZONE):
        bucket = self.bucket
        measurement = params.get('measurement')
        if not measurement or measurement == 'None':
            logger.error("Invalid or missing measurement in params")
            return None

        start_date = params.get('start_date')
        end_date = params.get('end_date')
        content_type = params.get('content_type')
        object_id = params.get('object_id')
        print(f"get_query called with params: {params}")
        import pdb; pdb.set_trace()
        def format_time(time_str):
            if time_str:
                try:
                    if isinstance(time_str, str):
                        # Try parsing as ISO format first
                        try:
                            dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                        except ValueError:
                            # If that fails, try parsing as a different format
                            dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                    else:
                        dt = time_str
                    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                except Exception as e:
                    print(f"Error parsing time: {e}")
                    return None

        start_date = format_time(start_date) if start_date else f'-{time}'
        end_date = format_time(end_date) if end_date else 'now()'

        flux_query = f'''
        from(bucket: "{bucket}")
            |> range(start: {start_date}, stop: {end_date})
            |> filter(fn: (r) => r._measurement == "{measurement}")
            |> filter(fn: (r) => r.content_type == "{content_type}" and r.object_id == "{object_id}")
        '''

        if not summary:
            window = group_map.get(time, '1h')
            flux_query += f'|> aggregateWindow(every: {window}, fn: mean, createEmpty: false)'

        flux_query += '''
            |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
        '''

        if summary:
            flux_query += '|> last()'

        flux_query += '|> yield(name: "result")'

        print(f"Generated Flux query: {flux_query}")
        return flux_query
    # def get_query(
    #     self,
    #     chart_type,
    #     params,
    #     time_range,
    #     group_map,
    #     summary=False,
    #     fields=None,
    #     query=None,
    #     timezone=settings.TIME_ZONE,
    # ):
    #     flux_query = f'from(bucket: "{self.bucket}")'

    #     def format_date(date):
    #         if date is None:
    #             return None
    #         if isinstance(date, str):
    #             try:
    #                 dt = datetime.strptime(date, "%Y-%m-%d %H:%M:%S")
    #                 return str(int(dt.timestamp()))
    #             except ValueError:
    #                 return date
    #         if isinstance(date, datetime):
    #             return str(int(date.timestamp()))
    #         return str(date)

    #     start_date = format_date(params.get('start_date'))
    #     end_date = format_date(params.get('end_date'))

    #     if start_date:
    #         flux_query += f' |> range(start: {start_date}'
    #     else:
    #         flux_query += f' |> range(start: -{time_range}'

    #     if end_date:
    #         flux_query += f', stop: {end_date})'
    #     else:
    #         flux_query += ')'

    #     if 'key' in params:
    #         flux_query += f' |> filter(fn: (r) => r._measurement == "{params["key"]}")'

    #     if fields and fields != '*':
    #         field_filters = ' or '.join([f'r._field == "{field.strip()}"' for field in fields.split(',')])
    #         flux_query += f' |> filter(fn: (r) => {field_filters})'

    #     if 'content_type' in params and 'object_id' in params:
    #         flux_query += f' |> filter(fn: (r) => r.content_type == "{params["content_type"]}" and r.object_id == "{params["object_id"]}")'

    #     window_period = group_map.get(time_range, '1h')
    #     if chart_type in ['line', 'stackedbar']:
    #         flux_query += f' |> aggregateWindow(every: {window_period}, fn: mean, createEmpty: false)'

    #     flux_query += ' |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")'

    #     if summary:
    #         flux_query += ' |> last()'

    #     flux_query = f'import "timezone"\n\noption location = timezone.location(name: "{timezone}")\n\n{flux_query}'

    #     flux_query += ' |> yield(name: "result")'

    #     print(f"Generated Flux query: {flux_query}")  # Debug print
    #     return flux_query

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

    def close(self):
        self.client.close()

#todo
# bucket_api.find_bucket_by_name("openwisp")
