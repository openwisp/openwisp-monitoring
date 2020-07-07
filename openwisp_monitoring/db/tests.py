from datetime import timedelta

from django.utils.timezone import now
from swapper import load_model

from . import timeseries_db
from .backends import load_backend_module

Chart = load_model('monitoring', 'Chart')
tests = load_backend_module(module='tests.client_tests')


class TestDatabaseClient(tests.TestDatabaseClient):
    def test_is_aggregate_bug(self):
        m = self._create_object_metric(name='summary_avg')
        c = Chart(metric=m, configuration='dummy')
        self.assertFalse(timeseries_db._is_aggregate(c.query))

    def test_is_aggregate_fields_function(self):
        m = self._create_object_metric(name='is_aggregate_func')
        c = Chart(metric=m, configuration='uptime')
        self.assertTrue(timeseries_db._is_aggregate(c.query))

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

    def test_read_order(self):
        timeseries_db.delete_metric_data()
        m = self._create_general_metric(name='dummy')
        m.write(40, time=now() - timedelta(days=2))
        m.write(30)
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
