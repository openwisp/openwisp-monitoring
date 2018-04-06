import json
from datetime import date, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils.timezone import now
from influxdb.exceptions import InfluxDBClientError

from . import TestMonitoringMixin
from ..models import Graph


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

    def test_read_multiple(self):
        g = self._create_graph(test_data=None)
        m1 = g.metric
        m2 = self._create_object_metric(name='test metric 2',
                                        key='test_metric',
                                        field_name='value2',
                                        content_object=m1.content_object)
        now_ = now()
        for n in range(0, 3):
            time = now_ - timedelta(days=n)
            m1.write(n + 1, time=time)
            m2.write(n + 2, time=time)
        g.query = g.query.replace('{field_name}', '{field_name}, value2')
        g.save()
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
        g = self._create_graph()
        g.query = 'BAD'
        with self.assertRaises(InfluxDBClientError):
            g.read()

    def test_save_bad_query(self):
        g = self._create_graph()
        g.query = 'BAD'
        try:
            g.full_clean()
        except ValidationError as e:
            self.assertIn('query', e.message_dict)
        else:
            self.fail('ValidationError not raised')

    def test_default_query(self):
        g = self._create_graph(test_data=False)
        q = "SELECT {field_name} FROM {key} WHERE time >= '{time}' AND " \
            "content_type = '{content_type}' AND object_id = '{object_id}'"
        self.assertEqual(g.query, q)

    def test_get_query(self):
        g = self._create_graph(test_data=False)
        m = g.metric
        time = date.today() - timedelta(days=6)
        expected = g.query.format(field_name=m.field_name,
                                  key=m.key,
                                  content_type=m.content_type_key,
                                  object_id=m.object_id,
                                  time=str(time))
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
            'SELECT * INTO metric2 FROM test_metric'
        ]
        for q in queries:
            g.query = q
            try:
                g.full_clean()
            except ValidationError as e:
                self.assertIn('query', e.message_dict)
            else:
                self.fail('ValidationError not raised')

    def test_description(self):
        g = self._create_graph(test_data=False)
        self.assertEqual(g.description, g.metric.name)
        g.description = 'test'
        g.full_clean()
        g.save()
        g.refresh_from_db()
        self.assertEqual(g.description, 'test')

    def test_wifi_hostapd(self):
        m = self._create_object_metric(name='wifi associations',
                                       key='hostapd',
                                       field_name='mac_address')
        g = self._create_graph(metric=m, test_data=False)
        for n in range(0, 9):
            m.write('00:16:3e:00:00:00', time=now() - timedelta(days=n))
            m.write('00:23:4b:00:00:00', time=now() - timedelta(days=n, seconds=1))
        m.write('00:16:3e:00:00:00', time=now() - timedelta(days=2))
        m.write('00:16:3e:00:00:00', time=now() - timedelta(days=4))
        m.write('00:23:4a:00:00:00')
        m.write('00:14:5c:00:00:00')
        q = "SELECT COUNT(DISTINCT({field_name})) AS {field_name} FROM {key} " \
            "WHERE time >= '{time}' AND content_type = '{content_type}' " \
            "AND object_id = '{object_id}' GROUP BY time(24h)"
        g.query = q
        g.save()
        data = g.read(time='30d')
        self.assertEqual(data['traces'][0][0], m.field_name)
        # last 10 days
        self.assertEqual(data['traces'][0][1][-10:], [0, 2, 2, 2, 2, 2, 2, 2, 2, 4])

    def test_get_query_1d(self):
        g = self._create_graph(test_data=None)
        g.query = g.query.replace('{field_name}', 'MEAN({field_name})')
        g.save()
        q = g.get_query(time='1d')
        last24 = now() - timedelta(days=1)
        self.assertIn(str(last24)[0:14], q)
        self.assertIn('group by time(10m)', q.lower())
        self.assertNotIn('fill(', q.lower())

    def test_get_query_30d(self):
        g = self._create_graph(test_data=None)
        q = "SELECT MEAN({field_name}) AS {field_name} FROM {key} " \
            "WHERE time >= '{time}' AND content_type = '{content_type}' " \
            "AND object_id = '{object_id}' GROUP BY time(5m) fill(0)"
        g.query = q
        g.save()
        q = g.get_query(time='30d')
        last30d = now() - timedelta(days=30)
        self.assertIn(str(last30d)[0:10], q)
        self.assertIn('group by time(24h)', q.lower())
        self.assertIn('fill(0)', q.lower())

    def test_get_time(self):
        g = Graph()
        self.assertIn(str(date.today() - timedelta(days=30)), g._get_time('30d'))
        self.assertIn(str(now() - timedelta(days=1))[0:10], g._get_time('1d'))
        self.assertIn(str(now() - timedelta(days=3))[0:10], g._get_time('3d'))
