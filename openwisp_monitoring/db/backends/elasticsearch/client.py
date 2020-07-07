import json
import logging
import re
from collections import Counter
from copy import deepcopy
from datetime import datetime, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.functional import cached_property
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ElasticsearchException, NotFoundError
from elasticsearch_dsl import Search
from elasticsearch_dsl.connections import connections
from pytz import timezone as tz

from openwisp_utils.utils import deep_merge_dicts

from ...exceptions import TimeseriesWriteException
from .. import TIMESERIES_DB
from .index import MetricDocument, Point, find_metric
from .queries import default_chart_query, math_map, operator_lookup
from .retention_policies import _make_policy, default_rp_policy

logger = logging.getLogger(__name__)


class DatabaseClient(object):
    _AGGREGATE = [
        'filters',
        'children',
        'parent',
        'date_histogram',
        'auto_date_histogram',
        'date_range',
        'geo_distance',
        'geohash_grid',
        'geotile_grid',
        'global',
        'geo_centroid',
        'global',
        'ip_range',
        'missing',
        'nested',
        'range',
        'reverse_nested',
        'significant_terms',
        'significant_text',
        'sampler',
        'terms',
        'diversified_sampler',
        'composite',
        'top_hits',
        'avg',
        'weighted_avg',
        'cardinality',
        'extended_stats',
        'geo_bounds',
        'max',
        'min',
        'percentiles',
        'percentile_ranks',
        'scripted_metric',
        'stats',
        'sum',
        'value_count',
    ]
    backend_name = 'elasticsearch'

    def __init__(self, db_name='metric'):
        self.db_name = db_name or TIMESERIES_DB['NAME']
        self.client_error = ElasticsearchException

    def create_database(self):
        """ creates connection to elasticsearch """
        connections.create_connection(
            hosts=[f"{TIMESERIES_DB['HOST']}:{TIMESERIES_DB['PORT']}"]
        )
        db = self.get_db
        # Skip if support for Index Lifecycle Management is disabled or no privileges
        self.ilm_enabled = db.ilm.start()['acknowledged']
        self.create_or_alter_retention_policy(name='default')

    def drop_database(self):
        """ deletes all indices """
        logger.debug('Deleted all indices data from Elasticsearch')

    @cached_property
    def get_db(self):
        """ Returns an ``Elasticsearch Client`` instance """
        return Elasticsearch(
            hosts=[{'host': TIMESERIES_DB['HOST'], 'port': TIMESERIES_DB['PORT']}],
            http_auth=(TIMESERIES_DB['USER'], TIMESERIES_DB['PASSWORD']),
            retry_on_timeout=True,
            # sniff before doing anything
            sniff_on_start=True,
            # refresh nodes after a node fails to respond
            sniff_on_connection_fail=True,
        )

    def create_or_alter_retention_policy(self, name, duration=None):
        """
        creates or alters existing retention policy if necessary

        Note: default retention policy can't be altered with this function
        """
        if not self.ilm_enabled:
            return
        ilm = self.get_db.ilm
        if not duration:
            try:
                ilm.get_lifecycle(policy='default')
            except NotFoundError:
                ilm.put_lifecycle(policy='default', body=default_rp_policy)
            return
        days = f'{int(duration.split("h")[0]) // 24}d'
        duration_changed = False
        try:
            policy = ilm.get_lifecycle(policy=name)
            exists = True
            current_duration = policy[name]['policy']['phases']['hot']['actions'][
                'rollover'
            ]['max_age']
            duration_changed = current_duration != days
        except NotFoundError:
            exists = False
        if not exists or duration_changed:
            policy = _make_policy(days)
            ilm.put_lifecycle(policy=name, body=policy)

    def get_list_retention_policies(self):
        if not self.ilm_enabled:
            return
        return self.get_db.ilm.get_lifecycle()

    def query(self, query, key=None, **kwargs):
        try:
            response = (
                Search(using=self.get_db, index=key)
                .update_from_dict(query)
                .execute()
                .to_dict()
            )
            if not response['hits']['total']['value']:
                return {}
            return response
        except NotFoundError:
            return {}

    def write(self, name, values, **kwargs):
        rp = kwargs.get('retention_policy')
        tags = kwargs.get('tags')
        timestamp = kwargs.get('timestamp')
        try:
            metric_id, index = find_metric(self.get_db, name, tags, rp, add=True)
            metric_index = MetricDocument.get(metric_id, index=index, using=self.get_db)
            point = Point(fields=values, time=timestamp or datetime.now())
            metric_index.points.append(point)
            metric_index.save()
        except Exception as exception:
            logger.warning(f'got exception while writing to tsdb: {exception}')
            raise TimeseriesWriteException
        # Elasticsearch automatically refreshes indices every second
        # but we can't wait that long especially for tests
        self.get_db.indices.refresh(index=name)

    def read(self, key, fields, tags=None, limit=1, order='time', **kwargs):
        """ ``since`` should be of the form 'now() - <int>s' """
        extra_fields = kwargs.get('extra_fields')
        time_format = kwargs.get('time_format')
        since = kwargs.get('since')
        try:
            metric_id, index = find_metric(self.get_db, key, tags)
        except TypeError:
            return []
        metric_index = MetricDocument.get(index=index, id=metric_id, using=self.get_db)
        # distinguish between traffic and clients
        points = []
        for point in list(metric_index.points):
            if fields in point.fields.to_dict():
                points.append(point)
        if order == 'time':
            points = points[0:limit]
        elif order == '-time':
            points = list(reversed(points))[0:limit]
        else:
            raise self.client_error(
                f'Invalid order "{order}" passed.\nYou may pass "time" / "-time" to get '
                'result sorted in ascending /descending order respectively.'
            )
        if extra_fields and extra_fields != '*':
            assert isinstance(extra_fields, list)
            for count, point in enumerate(points):
                fields_dict = point.to_dict()['fields']
                point = {
                    'time': self._format_time(point['time'], time_format),
                    fields: fields_dict[fields],
                }
                for extra_field in extra_fields:
                    if fields_dict.get(extra_field) is not None:
                        point.update({extra_field: fields_dict[extra_field]})
                points[count] = point
        elif extra_fields == '*':
            for count, point in enumerate(points):
                points[count] = deep_merge_dicts(
                    point.fields.to_dict(),
                    {'time': self._format_time(point.time, time_format)},
                )
        else:
            points = [
                deep_merge_dicts(
                    {fields: p.fields.to_dict()[fields]},
                    {'time': self._format_time(p.time, time_format)},
                )
                for p in points
            ]
        if since:
            since = datetime.now().timestamp() - int(re.search(r'\d+', since).group())
            points = [point for point in points if point['time'] >= since]
        return points

    def _format_time(self, obj, time_format=None):
        """ returns datetime object in isoformat / unix timestamp and UTC timezone """
        if time_format == 'isoformat':
            return obj.astimezone(tz=tz('UTC')).isoformat(timespec='seconds')
        return int(obj.astimezone(tz=tz('UTC')).timestamp())

    def get_list_query(self, query, precision='s', key=None):
        response = self.query(query, key)
        try:
            points = response['aggregations']['GroupByTime']['set_range']['time'][
                'buckets'
            ]
            list_points = self._fill_points(
                query, [self._format(point, precision) for point in points],
            )
            list_points.reverse()
        except KeyError:
            return []
        return list_points

    def _fill_points(self, query, points):
        _range = query['aggs']['GroupByTime']['nested']['aggs']['set_range']
        # if not _range or not points:
        #     return points
        days = int(_range['filter']['range']['points.time']['from'][4:-3])
        # return if summary query
        try:
            interval = _range['aggs']['time']['date_histogram']['fixed_interval']
        except KeyError:
            return points
        # return if top_fields query
        if interval == '365d':
            return points
        interval_dict = {'10m': 600, '20m': 1200, '1h': 3600, '24h': 86400}
        interval = interval_dict[interval]
        start_time = datetime.now()
        end_time = start_time - timedelta(days=days)  # include today
        dummy_point = deepcopy(points[0])
        start_ts = points[0]['time'] + interval
        end_ts = points[-1]['time'] - interval
        for field in dummy_point.keys():
            dummy_point[field] = None if field != 'wifi_clients' else 0
        while start_ts < start_time.timestamp():
            dummy_point['time'] = start_ts
            points.insert(0, deepcopy(dummy_point))
            start_ts += interval
        # TODO: This is required due to time_zone issues
        while points[-1]['time'] < end_time.timestamp():
            points.pop(-1)
        while end_ts > end_time.timestamp():
            dummy_point['time'] = end_ts
            points.append(deepcopy(dummy_point))
            end_ts -= interval
        return points

    def delete_metric_data(self, key=None, tags=None):
        """
        deletes a specific metric based on given key and tags;
        deletes all metrics if neither provided
        """
        if key and tags:
            metric_id, index = find_metric(self.get_db, key, tags)
            self.get_db.delete(index=index, id=metric_id)
        elif key:
            self.get_db.indices.delete_alias(
                index=f'{key}-*', name=key, ignore=[400, 404]
            )
        else:
            self.get_db.indices.delete(index='*', ignore=[400, 404])
            # TODO: Speed up tests by retaining indices, almost 50s difference on travis
            # try:
            #     self.get_db.delete_by_query(index='_all', body={'query': {'match_all': {}}})
            # except self.client_error:
            #     pass

    # Chart related functions below

    def validate_query(self, query):
        if not isinstance(query, dict):
            raise ValidationError(
                {'configuration': f'error parsing query: found {query}'}
            )
        # Elasticsearch currently supports validation of only query section,
        # aggs, size, _source etc. are not supported
        try:
            valid_check = self.get_db.indices.validate_query(
                body={'query': query['query']}, explain=True
            )
        except NotFoundError:
            return True
        # Show a helpful message for failure
        if not valid_check['valid']:
            raise ValidationError(valid_check['error'])
        return self._is_aggregate(query)

    def _is_aggregate(self, query):
        agg_dict = query['aggs']['GroupByTime']['nested']['aggs']['set_range']['aggs'][
            'time'
        ]['aggs']['nest']['nested']['aggs'].values()
        agg = []
        for item in agg_dict:
            agg.append(next(iter(item)))
        is_aggregate = True if set(agg) <= set(self._AGGREGATE) else False
        return is_aggregate if 'size' in query else False

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
        if not params.get('object_id'):
            del query['query']
        query = json.dumps(query)
        for k, v in params.items():
            query = query.replace('{' + k + '}', v)
        query = self._group_by(query, time, chart_type, group_map, strip=summary)
        set_range = query['aggs']['GroupByTime']['nested']['aggs']['set_range']['aggs'][
            'time'
        ]
        if fields:
            aggregate_dict = set_range['aggs']['nest']['nested']['aggs']
            agg = deepcopy(aggregate_dict).popitem()[1].popitem()[0]
            aggregate_dict.update(
                {
                    f'{field}': {agg: {'field': f'points.fields.{field}'}}
                    for field in fields
                }
            )
        try:
            set_range['date_histogram']['time_zone'] = timezone
        except KeyError:
            pass
        return query

    def _group_by(self, query, time, chart_type, group_map, strip=False):
        query = query.replace('1d/d', f'{time}/d')
        if not strip and not chart_type == 'histogram':
            value = group_map[time]
            query = query.replace('10m', value)
        if strip:
            query = json.loads(query)
            _range = query['aggs']['GroupByTime']['nested']['aggs']['set_range']['aggs']
            _range['time'].pop('date_histogram')
            _range['time']['auto_date_histogram'] = {
                'field': 'points.time',
                'format': 'date_time_no_millis',
                'buckets': 1,
            }
        if isinstance(query, str):
            query = json.loads(query)
        return query

    def _get_top_fields(
        self,
        params,
        chart_type,
        group_map,
        number,
        query=None,
        timezone=settings.TIME_ZONE,
        get_fields=True,
        **kwargs,
    ):
        """
        Returns top fields if ``get_fields`` set to ``True`` (default)
        else it returns points containing the top fields.
        """
        try:
            response = self.get_db.indices.get_mapping(index=params['key'])
        except NotFoundError:
            return []
        fields = [
            k
            for k, v in list(response.values())[0]['mappings']['properties']['points'][
                'properties'
            ]['fields']['properties'].items()
        ]
        query = self.get_query(
            chart_type=chart_type,
            params=params,
            time='365d',
            group_map=group_map,
            summary=True,
            fields=fields,
            query=query,
            timezone=timezone,
        )
        point = self.get_list_query(query, key=params['key'])[0]
        time = point.pop('time')
        point = Counter(point).most_common(number)
        if get_fields:
            return [k for k, v in point]
        points = [{'time': time}]
        for k, v in point:
            points[0][k] = v
        return points

    def _format(self, point, precision='s'):
        """ allowed values for precision are ``s`` and ``ms`` """
        pt = {}
        # By default values returned are in millisecond precision
        if precision == 'ms':
            pt['time'] = point['key'] / 1000
        else:
            pt['time'] = point['key'] // 1000
        for key, value in point.items():
            if isinstance(value, dict):
                for k, v in value.items():
                    if isinstance(v, dict):
                        pt[k] = self._transform_field(k, v['value'])
        return pt

    def _transform_field(self, field, value):
        """ Performs arithmetic operations on the field if required """
        if value is None:
            return value
        if field in math_map:
            op = operator_lookup.get(math_map[field]['operator'])
            if op is not None:
                value = op(value, math_map[field]['value'])
        return value

    def default_chart_query(self, tags=False):
        q = deepcopy(default_chart_query)
        # This is used to distinguish that it's default query
        del q['size']
        if not tags:
            q['query']['nested']['query']['bool']['must'] = []
        return q

    def _device_data(self, key, tags, fields, **kwargs):
        """ returns last snapshot of ``device_data`` """
        return self.read(
            key=key, fields=fields, tags=tags, order='-time', time_format='isoformat',
        )


# TODO:
# _fill_points has a while which shouldn't be required
