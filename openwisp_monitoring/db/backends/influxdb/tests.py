from datetime import datetime, timedelta
from unittest.mock import patch

from celery.exceptions import Retry
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils.timezone import now
from freezegun import freeze_time
from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBServerError
from pytz import timezone as tz
from swapper import load_model

from openwisp_monitoring.device.settings import SHORT_RETENTION_POLICY
from openwisp_monitoring.device.utils import SHORT_RP, manage_short_retention_policy
from openwisp_monitoring.monitoring.tests import TestMonitoringMixin

from ...exceptions import TimeseriesWriteException
from .. import timeseries_db

Chart = load_model('monitoring', 'Chart')
Notification = load_model('openwisp_notifications', 'Notification')


class TestDatabaseClient(TestMonitoringMixin, TestCase):
    def test_forbidden_queries(self):
        queries = [
            'DROP DATABASE openwisp2',
            'DROP MEASUREMENT test_metric',
            'CREATE DATABASE test',
            'DELETE MEASUREMENT test_metric',
            'ALTER RETENTION POLICY policy',
            'SELECT * INTO metric2 FROM test_metric',
        ]
        for q in queries:
            try:
                timeseries_db.validate_query(q)
            except ValidationError as e:
                self.assertIn('configuration', e.message_dict)
            else:
                self.fail('ValidationError not raised')

    def test_get_custom_query(self):
        c = self._create_chart(test_data=None)
        custom_q = c._default_query.replace('{field_name}', '{fields}')
        q = c.get_query(query=custom_q, fields=['SUM(*)'])
        self.assertIn('SELECT SUM(*) FROM', q)

    def test_is_aggregate_bug(self):
        m = self._create_object_metric(name='summary_avg')
        c = Chart(metric=m, configuration='dummy')
        self.assertFalse(timeseries_db._is_aggregate(c.query))

    def test_is_aggregate_fields_function(self):
        m = self._create_object_metric(name='is_aggregate_func')
        c = Chart(metric=m, configuration='uptime')
        self.assertTrue(timeseries_db._is_aggregate(c.query))

    def test_get_query_fields_function(self):
        c = self._create_chart(test_data=None, configuration='histogram')
        q = c.get_query(fields=['ssh', 'http2', 'apple-music'])
        expected = (
            'SELECT SUM("ssh") / 1 AS ssh, '
            'SUM("http2") / 1 AS http2, '
            'SUM("apple-music") / 1 AS apple_music FROM'
        )
        self.assertIn(expected, q)

    def test_default_query(self):
        c = self._create_chart(test_data=False)
        q = (
            "SELECT {field_name} FROM {key} WHERE time >= '{time}' AND "
            "content_type = '{content_type}' AND object_id = '{object_id}'"
        )
        self.assertEqual(c.query, q)

    def test_write(self):
        timeseries_db.write('test_write', dict(value=2), database=self.TEST_DB)
        measurement = list(
            timeseries_db.query(
                'select * from test_write', database=self.TEST_DB
            ).get_points()
        )[0]
        self.assertEqual(measurement['value'], 2)

    def test_general_write(self):
        m = self._create_general_metric(name='Sync test')
        m.write(1)
        measurement = list(timeseries_db.query('select * from sync_test').get_points())[
            0
        ]
        self.assertEqual(measurement['value'], 1)

    def test_object_write(self):
        om = self._create_object_metric()
        om.write(3)
        content_type = '.'.join(om.content_type.natural_key())
        q = (
            f"select * from test_metric WHERE object_id = '{om.object_id}'"
            f" AND content_type = '{content_type}'"
        )
        measurement = timeseries_db.get_list_query(q)[0]
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
        measurement = list(
            timeseries_db.query('select download from traffic').get_points()
        )[0]
        self.assertEqual(measurement['download'], 200)
        measurement = list(
            timeseries_db.query('select upload from traffic').get_points()
        )[0]
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
        content_type = '.'.join(user_down.content_type.natural_key())
        q = (
            f"select download from traffic WHERE object_id = '{user_down.object_id}'"
            f" AND content_type = '{content_type}'"
        )
        measurement = timeseries_db.get_list_query(q)[0]
        self.assertEqual(measurement['download'], 200)
        q = (
            f"select upload from traffic WHERE object_id = '{user_up.object_id}'"
            f" AND content_type = '{content_type}'"
        )
        measurement = timeseries_db.get_list_query(q)[0]
        self.assertEqual(measurement['upload'], 100)

    def test_delete_metric_data(self):
        m = self._create_general_metric(name='test_metric')
        m.write(100)
        self.assertEqual(m.read()[0]['value'], 100)
        timeseries_db.delete_metric_data(key=m.key)
        self.assertEqual(m.read(), [])
        om = self._create_object_metric(name='dummy')
        om.write(50)
        m.write(100)
        self.assertEqual(m.read()[0]['value'], 100)
        self.assertEqual(om.read()[0]['value'], 50)
        timeseries_db.delete_metric_data()
        self.assertEqual(m.read(), [])
        self.assertEqual(om.read(), [])

    def test_get_query_1d(self):
        c = self._create_chart(test_data=None, configuration='uptime')
        q = c.get_query(time='1d')
        last24 = now() - timedelta(days=1)
        self.assertIn(str(last24)[0:14], q)
        self.assertIn('group by time(10m)', q.lower())

    def test_get_query_30d(self):
        c = self._create_chart(test_data=None, configuration='uptime')
        q = c.get_query(time='30d')
        last30d = now() - timedelta(days=30)
        self.assertIn(str(last30d)[0:10], q)
        self.assertIn('group by time(24h)', q.lower())

    def test_retention_policy(self):
        manage_short_retention_policy()
        rp = timeseries_db.get_list_retention_policies()
        self.assertEqual(len(rp), 2)
        self.assertEqual(rp[1]['name'], SHORT_RP)
        self.assertEqual(rp[1]['default'], False)
        duration = SHORT_RETENTION_POLICY
        self.assertEqual(rp[1]['duration'], duration)

    def test_query_set(self):
        c = self._create_chart(configuration='histogram')
        expected = (
            "SELECT {fields|SUM|/ 1} FROM {key} "
            "WHERE time >= '{time}' AND content_type = "
            "'{content_type}' AND object_id = '{object_id}'"
        )
        self.assertEqual(c.query, expected)
        self.assertEqual(
            ''.join(timeseries_db.queries.default_chart_query[0:2]), c._default_query
        )
        c.metric.object_id = None
        self.assertEqual(timeseries_db.queries.default_chart_query[0], c._default_query)

    def test_read_order(self):
        m = self._create_general_metric(name='dummy')
        m.write(30)
        m.write(40, time=now() - timedelta(days=2))
        with self.subTest('Test ascending read order'):
            metric_data = m.read(limit=2, order='time')
            self.assertEqual(metric_data[0]['value'], 40)
            self.assertEqual(metric_data[1]['value'], 30)
        with self.subTest('Test descending read order'):
            metric_data = m.read(limit=2, order='-time')
            self.assertEqual(metric_data[0]['value'], 30)
            self.assertEqual(metric_data[1]['value'], 40)
        with self.subTest('Test invalid read order'):
            with self.assertRaises(timeseries_db.client_error) as e:
                metric_data = m.read(limit=2, order='invalid')
                self.assertIn('Invalid order "invalid" passed.', str(e))

    def test_read_with_rp(self):
        self._create_admin()
        manage_short_retention_policy()
        with self.subTest(
            'Test metric write on short retention_policy immediate alert'
        ):
            m = self._create_general_metric(name='dummy')
            self._create_alert_settings(
                metric=m, custom_operator='<', custom_threshold=1, custom_tolerance=0
            )
            m.write(0, retention_policy=SHORT_RP)
            self.assertEqual(m.read(retention_policy=SHORT_RP)[0][m.field_name], 0)
            m.refresh_from_db()
            self.assertFalse(m.is_healthy)
            self.assertEqual(Notification.objects.count(), 1)
        with self.subTest(
            'Test metric write on short retention_policy with deferred alert'
        ):
            m2 = self._create_general_metric(name='dummy2')
            self._create_alert_settings(
                metric=m2, custom_operator='<', custom_threshold=1, custom_tolerance=1
            )
            m.write(0, retention_policy=SHORT_RP, time=now() - timedelta(minutes=2))
            self.assertEqual(m.read(retention_policy=SHORT_RP)[0][m.field_name], 0)
            m.refresh_from_db()
            self.assertFalse(m.is_healthy)
            self.assertEqual(Notification.objects.count(), 1)

    def test_metric_write_microseconds_precision(self):
        m = self._create_object_metric(
            name='wlan0', key='wlan0', configuration='clients'
        )
        m.write('00:14:5c:00:00:00', time=datetime(2020, 7, 31, 22, 5, 47, 235142))
        m.write('00:23:4a:00:00:00', time=datetime(2020, 7, 31, 22, 5, 47, 235152))
        self.assertEqual(len(m.read()), 2)

    @patch.object(
        InfluxDBClient, 'write', side_effect=InfluxDBServerError('Server error')
    )
    def test_write_retry(self, mock_write):
        with self.assertRaises(TimeseriesWriteException):
            timeseries_db.write('test_write', {'value': 1})
        m = self._create_general_metric(name='Test metric')
        with self.assertRaises(Retry):
            m.write(1)

    @patch.object(
        InfluxDBClient, 'write', side_effect=InfluxDBServerError('Server error')
    )
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
