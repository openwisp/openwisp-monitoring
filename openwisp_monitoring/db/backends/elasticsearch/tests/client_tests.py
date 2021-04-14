from datetime import datetime, timedelta
from importlib import reload
from unittest.mock import patch

from celery.exceptions import Retry
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.timezone import now
from elasticsearch.exceptions import ElasticsearchException
from freezegun import freeze_time
from pytz import timezone as tz

from openwisp_monitoring.device.settings import SHORT_RETENTION_POLICY
from openwisp_monitoring.device.tests import DeviceMonitoringTestCase
from openwisp_monitoring.device.utils import SHORT_RP, manage_short_retention_policy

from ....exceptions import TimeseriesWriteException
from ... import timeseries_db
from .. import queries as queries_module
from ..index import MetricDocument


class TestDatabaseClient(DeviceMonitoringTestCase):
    def test_get_query_fields_function(self):
        c = self._create_chart(test_data=None, configuration='histogram')
        q = c.get_query(fields=['ssh', 'http2', 'apple-music'])
        self.assertIn("'ssh': {'sum': {'field': 'points.fields.ssh'}}", str(q))
        self.assertIn("'http2': {'sum': {'field': 'points.fields.http2'}}", str(q))
        self.assertIn(
            "'apple-music': {'sum': {'field': 'points.fields.apple-music'}}", str(q)
        )

    def test_default_query(self):
        c = self._create_chart(test_data=False)
        q = timeseries_db.default_chart_query(tags=True)
        self.assertEqual(c.query, q)

    def test_write(self):
        timeseries_db.write('test_write', dict(value=2))
        measurement = timeseries_db.read(key='test_write', fields='value')[0]
        self.assertEqual(measurement['value'], 2)

    def test_general_write(self):
        m = self._create_general_metric(name='Sync test')
        m.write(1)
        measurement = timeseries_db.read(key='sync_test', fields='value')[0]
        self.assertEqual(measurement['value'], 1)

    def test_object_write(self):
        om = self._create_object_metric()
        om.write(3)
        measurement = timeseries_db.read(
            key='test_metric', fields='value', tags=om.tags
        )[0]
        self.assertEqual(measurement['value'], 3)

    def test_general_same_key_different_fields(self):
        down = self._create_general_metric(
            name='traffic (download)', key='traffic', field_name='download'
        )
        down.write(200)
        up = self._create_general_metric(
            name='traffic (upload)', key='traffic', field_name='upload'
        )
        up.write(100)
        measurement = timeseries_db.read(key='traffic', fields='download')[0]
        self.assertEqual(measurement['download'], 200)
        measurement = timeseries_db.read(key='traffic', fields='upload')[0]
        self.assertEqual(measurement['upload'], 100)

    def test_object_same_key_different_fields(self):
        user = self._create_user()
        user_down = self._create_object_metric(
            name='traffic (download)',
            key='traffic',
            field_name='download',
            content_object=user,
        )
        user_down.write(200)
        user_up = self._create_object_metric(
            name='traffic (upload)',
            key='traffic',
            field_name='upload',
            content_object=user,
        )
        user_up.write(100)
        measurement = timeseries_db.read(
            key='traffic', fields='download', tags=user_down.tags
        )[0]
        self.assertEqual(measurement['download'], 200)
        measurement = timeseries_db.read(
            key='traffic', fields='upload', tags=user_up.tags
        )[0]
        self.assertEqual(measurement['upload'], 100)

    def test_get_query_1d(self):
        c = self._create_chart(test_data=None, configuration='uptime')
        q = c.get_query(time='1d')
        time_map = c.GROUP_MAP['1d']
        self.assertIn(
            "{'range': {'points.time': {'from': 'now-1d/d', 'to': 'now/d'}}}", str(q)
        )
        self.assertIn(f"'fixed_interval': '{time_map}'", str(q))

    def test_get_query_30d(self):
        c = self._create_chart(test_data=None, configuration='uptime')
        q = c.get_query(time='30d')
        time_map = c.GROUP_MAP['30d']
        self.assertIn(
            "{'range': {'points.time': {'from': 'now-30d/d', 'to': 'now/d'}}}", str(q)
        )
        self.assertIn(f"'fixed_interval': '{time_map}'", str(q))

    def test_retention_policy(self):
        manage_short_retention_policy()
        rp = timeseries_db.get_list_retention_policies()
        assert 'default' in rp
        assert SHORT_RP in rp
        days = f'{int(SHORT_RETENTION_POLICY.split("h")[0]) // 24}d'
        self.assertEqual(
            rp['short']['policy']['phases']['hot']['actions']['rollover']['max_age'],
            days,
        )

    def test_get_query(self):
        c = self._create_chart(test_data=False)
        m = c.metric
        params = dict(
            field_name=m.field_name,
            key=m.key,
            content_type=m.content_type_key,
            object_id=m.object_id,
            time=c.DEFAULT_TIME,
        )
        expected = timeseries_db.get_query(
            c.type,
            params,
            c.DEFAULT_TIME,
            c.GROUP_MAP,
            query=c.query,
            timezone=settings.TIME_ZONE,
        )
        self.assertEqual(c.get_query(), expected)

    def test_query_no_index(self):
        timeseries_db.delete_metric_data(key='ping')
        c = self._create_chart(test_data=False)
        q = c.get_query()
        self.assertEqual(timeseries_db.query(q, index='ping'), {})
        self.assertEqual(timeseries_db.get_list_query(q), [])

    def test_1d_chart_data(self):
        c = self._create_chart()
        data = c.read(time='1d')
        self.assertIn('x', data)
        self.assertEqual(len(data['x']), 144)
        self.assertIn('traces', data)
        self.assertEqual(9.0, data['traces'][0][1][-1])
        # Test chart with old data has same length
        m = self._create_general_metric(name='dummy')
        c = self._create_chart(metric=m, test_data=False)
        m.write(6.0, time=now() - timedelta(hours=23))
        data = c.read(time='1d')
        self.assertIn('x', data)
        self.assertEqual(len(data['x']), 144)
        self.assertIn('traces', data)
        self.assertIn(6.0, data['traces'][0][1])

    def test_delete_metric_data(self):
        obj = self._create_user()
        om = self._create_object_metric(name='Logins', content_object=obj)
        om.write(100)
        self.assertEqual(om.read()[0]['value'], 100)
        timeseries_db.delete_metric_data(key=om.key, tags=om.tags)

    def test_invalid_query(self):
        q = timeseries_db.default_chart_query()
        q['query']['nested']['query']['must'] = 'invalid'
        try:
            timeseries_db.validate_query(q)
        except ValidationError as e:
            self.assertIn('ParsingException: [bool] malformed query', str(e))

    def test_non_aggregation_query(self):
        q = {'query': timeseries_db.default_chart_query()['query']}
        self.assertEqual(timeseries_db.get_list_query(q), [])

    def test_timestamp_precision(self):
        c = self._create_chart()
        points = timeseries_db.get_list_query(c.get_query(), precision='ms')
        self.assertIsInstance(points[0]['time'], float)
        points = timeseries_db.get_list_query(c.get_query(), precision='s')
        self.assertIsInstance(points[0]['time'], int)

    def create_docs_single_index(self):
        m = self._create_object_metric(name='dummy')
        m.write(1)
        d = self._create_device(organization=self._create_org())
        m2 = self._create_object_metric(name='dummy', content_object=d)
        m2.write(1)
        self.assertEqual(len(timeseries_db.get_db.indices.get_alias(name='dummy')), 1)

    def test_additional_chart_operations_setting(self):
        modify_operators = {
            'upload': {'operator': '/', 'value': 1000000},
            'download': {'operator': '/', 'value': 1000000},
        }
        path = 'openwisp_monitoring.db.backends.elasticsearch.queries.ADDITIONAL_CHART_OPERATIONS'
        with patch.dict(path, modify_operators, clear=True):
            queries = reload(queries_module)
            self.assertEqual(queries.ADDITIONAL_CHART_OPERATIONS, modify_operators)
            self.assertEqual(queries.math_map['upload'], modify_operators['upload'])
            self.assertEqual(queries.math_map['download'], modify_operators['download'])

    def test_read(self):
        c = self._create_chart()
        data = c.read()
        key = c.metric.field_name
        self.assertIn('x', data)
        self.assertIn('traces', data)
        self.assertEqual(len(data['x']), 168)
        charts = data['traces']
        self.assertEqual(charts[0][0], key)
        self.assertEqual(len(charts[0][1]), 168)
        self.assertTrue(all(elem in charts[0][1] for elem in [3, 6, 9]))

    def test_read_multiple(self):
        c = self._create_chart(test_data=None, configuration='multiple_test')
        m1 = c.metric
        m2 = self._create_object_metric(
            name='test metric 2',
            key='test_metric',
            field_name='value2',
            content_object=m1.content_object,
        )
        now_ = now()
        for n in range(0, 3):
            time = now_ - timedelta(days=n)
            m1.write(n + 1, time=time)
            m2.write(n + 2, time=time)
        data = c.read()
        f1 = m1.field_name
        f2 = 'value2'
        self.assertIn('x', data)
        self.assertIn('traces', data)
        self.assertEqual(len(data['x']), 168)
        charts = data['traces']
        self.assertIn(f1, charts[0][0])
        self.assertIn(f2, charts[1][0])
        self.assertEqual(len(charts[0][1]), 168)
        self.assertEqual(len(charts[1][1]), 168)
        self.assertTrue(all(elem in charts[0][1] for elem in [3, 2, 1]))
        self.assertTrue(all(elem in charts[1][1] for elem in [4, 3, 2]))

    def test_ilm_disabled(self):
        with patch.object(timeseries_db, 'ilm_enabled', False):
            self.assertFalse(timeseries_db.ilm_enabled)
            self.assertIsNone(
                timeseries_db.create_or_alter_retention_policy(name='default')
            )
            self.assertIsNone(timeseries_db.get_list_retention_policies())

    @patch.object(MetricDocument, 'get', side_effect=ElasticsearchException)
    def test_write_retry(self, mock_write):
        with self.assertRaises(TimeseriesWriteException):
            timeseries_db.write('test_write', {'value': 1})
        m = self._create_general_metric(name='Test metric')
        with self.assertRaises(Retry):
            m.write(1)

    @patch.object(MetricDocument, 'get', side_effect=ElasticsearchException)
    def test_timeseries_write_params(self, mock_write):
        with freeze_time('Jan 14th, 2020') as frozen_datetime:
            m = self._create_general_metric(name='Test metric')
            with self.assertRaises(Retry) as e:
                m.write(1)
            frozen_datetime.tick(delta=timedelta(minutes=10))
            self.assertEqual(
                now(), datetime(2020, 1, 14, tzinfo=tz('UTC')) + timedelta(minutes=10)
            )
            task_signature = e.exception.sig
            with patch.object(timeseries_db, 'write') as mock_write:
                self._retry_task(task_signature)
            mock_write.assert_called_with(
                'test_metric',
                {'value': 1},
                database=None,
                retention_policy=None,
                tags={},
                # this should be the original time at the moment of first failure
                timestamp='2020-01-14T00:00:00Z',
            )

    def _retry_task(self, task_signature):
        task_kwargs = task_signature.kwargs
        task_signature.type.run(**task_kwargs)
