from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils.timezone import now
from openwisp_monitoring.device.settings import SHORT_RETENTION_POLICY
from openwisp_monitoring.device.utils import SHORT_RP, manage_short_retention_policy
from openwisp_monitoring.monitoring.tests import TestMonitoringMixin
from swapper import load_model

from .. import timeseries_db

Chart = load_model('monitoring', 'Chart')


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
        self.assertEqual(rp[1]['duration'], SHORT_RETENTION_POLICY)

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
