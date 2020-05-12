import json
from datetime import date, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils.timezone import now

from ..models import Graph
from . import TestMonitoringMixin


class TestGraphs(TestMonitoringMixin, TestCase):
    """
    Tests for functionalities related to graphs
    """

    def test_read(self):
        g = self._create_graph()
        data = g.read()
        key = g.metric.field_name
        self.assertIn('x', data)
        self.assertIn('traces', data)
        self.assertEqual(len(data['x']), 3)
        graphs = data['traces']
        self.assertEqual(graphs[0][0], key)
        self.assertEqual(len(graphs[0][1]), 3)
        self.assertEqual(graphs[0][1], [3, 6, 9])

    def test_read_summary_avg(self):
        m = self._create_object_metric(name='summary_avg')
        g = self._create_graph(metric=m, test_data=False, configuration='mean_test')
        m.write(1, time=now() - timedelta(days=2))
        m.write(2, time=now() - timedelta(days=1))
        m.write(3, time=now())
        data = g.read()
        self.assertEqual(data['summary'], {'value': 2})

    def test_read_summary_sum(self):
        m = self._create_object_metric(name='summary_sum')
        g = self._create_graph(metric=m, test_data=False, configuration='sum_test')
        m.write(5, time=now() - timedelta(days=2))
        m.write(4, time=now() - timedelta(days=1))
        m.write(1, time=now())
        data = g.read()
        self.assertEqual(data['summary'], {'value': 10})

    def test_read_summary_not_aggregate(self):
        m = self._create_object_metric(name='summary_hidden')
        g = self._create_graph(metric=m)
        data = g.read()
        self.assertEqual(data['summary'], {'value': None})

    def test_read_summary_top_fields(self):
        m = self._create_object_metric(name='applications')
        g = self._create_graph(
            metric=m, test_data=False, configuration='top_fields_mean'
        )
        m.write(
            0,
            extra_values={
                'google': 150.00000001,
                'facebook': 0.00911111,
                'reddit': 0.0,
            },
            time=now() - timedelta(days=2),
        )
        m.write(
            0,
            extra_values={
                'google': 200.00000001,
                'facebook': 0.00611111,
                'reddit': 0.0,
            },
            time=now() - timedelta(days=1),
        )
        m.write(
            0,
            extra_values={
                'google': 250.00000001,
                'facebook': 0.00311111,
                'reddit': 0.0,
            },
            time=now() - timedelta(days=0),
        )
        data = g.read()
        self.assertEqual(data['summary'], {'google': 200.0, 'facebook': 0.0061})

    def test_read_summary_top_fields_acid(self):
        m = self._create_object_metric(name='applications')
        g = self._create_graph(
            metric=m, test_data=False, configuration='top_fields_mean'
        )
        m.write(
            0,
            extra_values={'google': 0.0, 'facebook': 6000.0, 'reddit': 0.0},
            time=now() - timedelta(days=3),
        )
        m.write(
            0,
            extra_values={
                'google': 150000000.0,
                'facebook': 90000000.0,
                'reddit': 1000.0,
            },
            time=now() - timedelta(days=2),
        )
        m.write(
            0,
            extra_values={'google': 200000000.0, 'facebook': 60000000.0, 'reddit': 0.0},
            time=now() - timedelta(days=1),
        )
        m.write(
            0,
            extra_values={'google': 0.0, 'facebook': 6000.0, 'reddit': 0.0},
            time=now() - timedelta(days=0),
        )
        data = g.read()
        self.assertEqual(data['summary'], {'google': 87500000, 'facebook': 37503000})
        self.assertEqual(g._get_top_fields(2), ['google', 'facebook'])

    def test_read_multiple(self):
        g = self._create_graph(test_data=None, configuration='multiple_test')
        m1 = g.metric
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
        data = g.read()
        f1 = m1.field_name
        f2 = 'value2'
        self.assertIn('x', data)
        self.assertIn('traces', data)
        self.assertEqual(len(data['x']), 3)
        graphs = data['traces']
        self.assertIn(f1, graphs[0][0])
        self.assertIn(f2, graphs[1][0])
        self.assertEqual(len(graphs[0][1]), 3)
        self.assertEqual(len(graphs[1][1]), 3)
        self.assertEqual(graphs[0][1], [3, 2, 1])
        self.assertEqual(graphs[1][1], [4, 3, 2])

    def test_json(self):
        g = self._create_graph()
        data = g.read()
        # convert tuples to lists otherwise comparison will fail
        for i, graph in enumerate(data['traces']):
            data['traces'][i] = list(graph)
        self.assertDictEqual(json.loads(g.json()), data)

    def test_read_bad_query(self):
        try:
            self._create_graph(configuration='bad_test')
        except ValidationError as e:
            self.assertIn('configuration', e.message_dict)
            self.assertIn('error parsing query: found BAD', str(e.message_dict))
        else:
            self.fail('ValidationError not raised')

    def test_default_query(self):
        g = self._create_graph(test_data=False)
        q = (
            "SELECT {field_name} FROM {key} WHERE time >= '{time}' AND "
            "content_type = '{content_type}' AND object_id = '{object_id}'"
        )
        self.assertEqual(g.query, q)

    def test_get_query(self):
        g = self._create_graph(test_data=False)
        m = g.metric
        now_ = now()
        today = date(now_.year, now_.month, now_.day)
        time = today - timedelta(days=6)
        expected = g.query.format(
            field_name=m.field_name,
            key=m.key,
            content_type=m.content_type_key,
            object_id=m.object_id,
            time=str(time),
        )
        expected = "{0} tz('{1}')".format(expected, settings.TIME_ZONE)
        self.assertEqual(g.get_query(), expected)

    def test_forbidden_queries(self):
        g = self._create_graph(test_data=False)
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
                g._is_query_allowed(q)
            except ValidationError as e:
                self.assertIn('configuration', e.message_dict)
            else:
                self.fail('ValidationError not raised')

    def test_description(self):
        g = self._create_graph(test_data=False)
        self.assertEqual(g.description, 'Dummy chart for testing purposes.')

    def test_wifi_hostapd(self):
        m = self._create_object_metric(
            name='wifi associations', key='hostapd', field_name='mac_address'
        )
        g = self._create_graph(metric=m, test_data=False, configuration='wifi_clients')
        for n in range(0, 9):
            m.write('00:16:3e:00:00:00', time=now() - timedelta(days=n))
            m.write('00:23:4b:00:00:00', time=now() - timedelta(days=n, seconds=1))
        m.write('00:16:3e:00:00:00', time=now() - timedelta(days=2))
        m.write('00:16:3e:00:00:00', time=now() - timedelta(days=4))
        m.write('00:23:4a:00:00:00')
        m.write('00:14:5c:00:00:00')
        g.save()
        data = g.read(time='30d')
        self.assertEqual(data['traces'][0][0], 'wifi_clients')
        # last 10 days
        self.assertEqual(data['traces'][0][1][-10:], [0, 2, 2, 2, 2, 2, 2, 2, 2, 4])

    def test_get_query_1d(self):
        g = self._create_graph(test_data=None, configuration='uptime')
        q = g.get_query(time='1d')
        last24 = now() - timedelta(days=1)
        self.assertIn(str(last24)[0:14], q)
        self.assertIn('group by time(10m)', q.lower())

    def test_get_query_30d(self):
        g = self._create_graph(test_data=None, configuration='uptime')
        q = g.get_query(time='30d')
        last30d = now() - timedelta(days=30)
        self.assertIn(str(last30d)[0:10], q)
        self.assertIn('group by time(24h)', q.lower())

    def test_get_time(self):
        g = Graph()
        now_ = now()
        today = date(now_.year, now_.month, now_.day)
        self.assertIn(str(today - timedelta(days=30)), g._get_time('30d'))
        self.assertIn(str(now() - timedelta(days=1))[0:10], g._get_time('1d'))
        self.assertIn(str(now() - timedelta(days=3))[0:10], g._get_time('3d'))

    def test_get_query_fields_function(self):
        g = self._create_graph(test_data=None, configuration='histogram')
        q = g.get_query(fields=['ssh', 'http2', 'apple-music'])
        expected = (
            'SELECT SUM("ssh") / 1 AS ssh, '
            'SUM("http2") / 1 AS http2, '
            'SUM("apple-music") / 1 AS apple_music FROM'
        )
        self.assertIn(expected, q)

    def test_get_custom_query(self):
        g = self._create_graph(test_data=None)
        custom_q = g._default_query.replace('{field_name}', '{fields}')
        q = g.get_query(query=custom_q, fields=['SUM(*)'])
        self.assertIn('SELECT SUM(*) FROM', q)

    def test_get_top_fields(self):
        g = self._create_graph(test_data=None, configuration='histogram')
        g.metric.write(
            None, extra_values={'http2': 100, 'ssh': 90, 'udp': 80, 'spdy': 70}
        )
        self.assertEqual(g._get_top_fields(number=3), ['http2', 'ssh', 'udp'])

    def test_is_aggregate_bug(self):
        m = self._create_object_metric(name='summary_avg')
        g = Graph(metric=m, configuration='dummy')
        self.assertFalse(g._is_aggregate(g.query))

    def test_is_aggregate_fields_function(self):
        m = self._create_object_metric(name='is_aggregate_func')
        g = Graph(metric=m, configuration='uptime')
        self.assertTrue(g._is_aggregate(g.query))

    def test_query_histogram(self):
        m = self._create_object_metric(name='histogram')
        m.write(None, extra_values={'http2': 100, 'ssh': 90, 'udp': 80, 'spdy': 70})
        g = Graph(metric=m, configuration='histogram')
        g.full_clean()
        g.save()
        self.assertNotIn('GROUP BY time', g.get_query())

    def test_bad_json_query_returns_none(self):
        m = self._create_object_metric(
            name='wifi associations', key='hostapd', field_name='mac_address'
        )
        g = self._create_graph(metric=m, test_data=False, configuration='wifi_clients')
        m.write('00:14:5c:00:00:00')
        g.save()
        self.assertIsNone(g.json(time=1))
