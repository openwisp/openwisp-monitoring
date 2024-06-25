import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from django.utils.timezone import now
from django.core.exceptions import ValidationError
from freezegun import freeze_time
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.rest import ApiException
from openwisp_monitoring.db.backends.influxdb2.client import DatabaseClient
from openwisp_monitoring.monitoring.tests import TestMonitoringMixin
from openwisp_monitoring.device.settings import DEFAULT_RETENTION_POLICY, SHORT_RETENTION_POLICY
from openwisp_monitoring.device.utils import DEFAULT_RP, SHORT_RP
from openwisp_monitoring.views import Chart

from ...exceptions import TimeseriesWriteException
from django.conf import settings

class TestDatabaseClient(TestMonitoringMixin, unittest.TestCase):
    def setUp(self):
        self.client = DatabaseClient(bucket="mybucket", org="myorg", token="dltiEmsmMKU__9SoBE0ingFdMTS3UksrESwIQDNtW_3WOgn8bQGdyYzPcx_aDtvZkqvR8RbMkwVVlzUJxpm62w==", url="http://localhost:8086")

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
            with self.assertRaises(ValidationError):
                self.client.validate_query(q)

    @patch('influxdb_client.InfluxDBClient')
    def test_write(self, mock_influxdb_client):
        mock_write_api = MagicMock()
        mock_influxdb_client.return_value.write_api.return_value = mock_write_api

        self.client.write('test_write', {'value': 2})
        
        mock_write_api.write.assert_called_once()
        call_args = mock_write_api.write.call_args[1]
        self.assertEqual(call_args['bucket'], 'mybucket')
        self.assertEqual(call_args['org'], 'myorg')
        self.assertIn('record', call_args)
        self.assertEqual(call_args['record']['measurement'], 'ping')
        self.assertEqual(call_args['record']['fields'], {'value': 2})

    @patch('influxdb_client.InfluxDBClient')
    def test_read(self, mock_influxdb_client):
        mock_query_api = MagicMock()
        mock_influxdb_client.return_value.query_api.return_value = mock_query_api

        self.client.read('ping', 'field1, field2', {'tag1': 'value1'})
        
        mock_query_api.query.assert_called_once()
        query = mock_query_api.query.call_args[0][0]
        self.assertIn('from(bucket: "mybucket")', query)
        self.assertIn('|> filter(fn: (r) => r._measurement == "ping")', query)
        self.assertIn('|> filter(fn: (r) => r._field == "field1" or r._field == "field2")', query)
        self.assertIn('|> filter(fn: (r) => r["tag1"] == "value1")', query)

    def test_validate_query(self):
        valid_query = 'from(bucket:"mybucket") |> range(start: -1h) |> filter(fn: (r) => r._measurement == "cpu")'
        self.assertTrue(self.client.validate_query(valid_query))

        invalid_query = 'DROP DATABASE test'
        with self.assertRaises(ValidationError):
            self.client.validate_query(invalid_query)

    def test_get_query_with_pdb(self):
        # Create a metric
        metric = self._create_object_metric(
            name='Ping',
            key='ping',  
            field_name='rtt_avg',
            content_type='config.device',
        )
        chart = self._create_chart(
            metric=metric,
            configuration='line',  
            test_data=False
        )

        time = '30d'
        group_map = Chart._get_group_map(time)
        query = chart.get_query(
            time=time,
            summary=False,
            fields=['loss', 'reachable', 'rtt_avg'],
            timezone='UTC'
        )
        self.assertIsNotNone(query)
        self.assertIn('from(bucket: "mybucket")', query)
        self.assertIn('range(start: -30d', query)
        self.assertIn('filter(fn: (r) => r._measurement == "ping")', query)

    @patch('influxdb_client.InfluxDBClient')
    def test_create_database(self, mock_influxdb_client):
        mock_bucket_api = MagicMock()
        mock_influxdb_client.return_value.buckets_api.return_value = mock_bucket_api

        self.client.create_database()        
        mock_bucket_api.find_bucket_by_name.assert_called_once_with('mybucket')
        mock_bucket_api.create_bucket.assert_called_once()

    @patch('influxdb_client.InfluxDBClient')
    def test_drop_database(self, mock_influxdb_client):
        mock_bucket_api = MagicMock()
        mock_influxdb_client.return_value.buckets_api.return_value = mock_bucket_api

        self.client.drop_database()
        
        mock_bucket_api.find_bucket_by_name.assert_called_once_with('mybucket')
        mock_bucket_api.delete_bucket.assert_called_once()

    @patch('influxdb_client.InfluxDBClient')
    def test_query(self, mock_influxdb_client):
        mock_query_api = MagicMock()
        mock_influxdb_client.return_value.query_api.return_value = mock_query_api

        test_query = 'from(bucket:"mybucket") |> range(start: -1h) |> filter(fn: (r) => r._measurement == "cpu")'
        self.client.query(test_query)
        
        mock_query_api.query.assert_called_once_with(test_query)

    def test_get_timestamp(self):
        timestamp = datetime(2023, 1, 1, 12, 0, 0)
        result = self.client._get_timestamp(timestamp)
        self.assertEqual(result, '2023-01-01T12:00:00.000000')

    @patch('influxdb_client.InfluxDBClient')
    def test_write_exception(self, mock_influxdb_client):
        mock_write_api = MagicMock()
        mock_write_api.write.side_effect = ApiException(status=500, reason="Server Error")
        mock_influxdb_client.return_value.write_api.return_value = mock_write_api

        with self.assertRaises(Exception):
            self.client.write('ping', {'value': 2})

    def test_get_custom_query(self):
        c = self._create_chart(test_data=None)
        custom_q = c._default_query.replace('{field_name}', '{fields}')
        q = c.get_query(query=custom_q, fields=['SUM(*)'])
        self.assertIn('SELECT SUM(*) FROM', q)

    def test_is_aggregate_bug(self):
        m = self._create_object_metric(name='summary_avg')
        c = self._create_chart(metric=m, configuration='dummy')
        self.assertFalse(self.client._is_aggregate(c.query))

    def test_is_aggregate_fields_function(self):
        m = self._create_object_metric(name='is_aggregate_func')
        c = self._create_chart(metric=m, configuration='uptime')
        self.assertTrue(self.client._is_aggregate(c.query))

    def test_get_query_fields_function(self):
        c = self._create_chart(test_data=None, configuration='histogram')
        q = c.get_query(fields=['ssh', 'http2', 'apple-music'])
        expected = (
            'SELECT SUM("ssh") / 1 AS ssh, '
            'SUM("http2") / 1 AS http2, '
            'SUM("apple-music") / 1 AS apple_music FROM'
        )
        self.assertIn(expected, q)

    @patch('influxdb_client.InfluxDBClient')
    def test_general_write(self, mock_influxdb_client):
        mock_write_api = MagicMock()
        mock_influxdb_client.return_value.write_api.return_value = mock_write_api

        m = self._create_general_metric(name='Sync test')
        m.write(1)
        
        mock_write_api.write.assert_called_once()
        call_args = mock_write_api.write.call_args[1]
        self.assertEqual(call_args['record']['measurement'], 'sync_test')
        self.assertEqual(call_args['record']['fields']['value'], 1)

    @patch('influxdb_client.InfluxDBClient')
    def test_object_write(self, mock_influxdb_client):
        mock_write_api = MagicMock()
        mock_influxdb_client.return_value.write_api.return_value = mock_write_api

        om = self._create_object_metric()
        om.write(3)
        
        mock_write_api.write.assert_called_once()
        call_args = mock_write_api.write.call_args[1]
        self.assertEqual(call_args['record']['measurement'], 'ping')
        self.assertEqual(call_args['record']['fields']['value'], 3)
        self.assertEqual(call_args['record']['tags']['object_id'], str(om.object_id))
        self.assertEqual(call_args['record']['tags']['content_type'], '.'.join(om.content_type.natural_key()))

    @patch('influxdb_client.InfluxDBClient')
    def test_delete_metric_data(self, mock_influxdb_client):
        mock_delete_api = MagicMock()
        mock_influxdb_client.return_value.delete_api.return_value = mock_delete_api

        self.client.delete_metric_data(key='ping')
        
        mock_delete_api.delete.assert_called_once()
        call_args = mock_delete_api.delete.call_args[1]
        self.assertIn('_measurement="ping"', call_args['predicate'])

    def test_get_query_1d(self):
        c = self._create_chart(test_data=None, configuration='uptime')
        q = c.get_query(time='1d')
        last24 = now() - timedelta(days=1)
        self.assertIn(str(last24)[0:14], q)
        self.assertIn('aggregateWindow(every: 10m', q)

    def test_get_query_30d(self):
        c = self._create_chart(test_data=None, configuration='uptime')
        q = c.get_query(time='30d')
        last30d = now() - timedelta(days=30)
        self.assertIn(str(last30d)[0:10], q)
        self.assertIn('aggregateWindow(every: 24h', q)

    @patch('influxdb_client.InfluxDBClient')
    @freeze_time("2023-01-01")
    def test_read_order(self, mock_influxdb_client):
        mock_query_api = MagicMock()
        mock_influxdb_client.return_value.query_api.return_value = mock_query_api

        m = self._create_general_metric(name='dummy')
        m.write(30)
        m.write(40, time=now() - timedelta(days=2))

        # Test ascending read order
        m.read(limit=2, order='time')
        query = mock_query_api.query.call_args[0][0]
        self.assertIn('|> sort(columns: ["_time"], desc: false)', query)

        # Test descending read order
        m.read(limit=2, order='-time')
        query = mock_query_api.query.call_args[0][0]
        self.assertIn('|> sort(columns: ["_time"], desc: true)', query)

        # Test invalid read order
        with self.assertRaises(ValueError):
            m.read(limit=2, order='invalid')

    @patch('influxdb_client.InfluxDBClient')
    def ping_write_microseconds_precision(self, mock_influxdb_client):
        mock_write_api = MagicMock()
        mock_influxdb_client.return_value.write_api.return_value = mock_write_api

        m = self._create_object_metric(name='wlan0', key='wlan0', configuration='clients')
        m.write('00:14:5c:00:00:00', time=datetime(2020, 7, 31, 22, 5, 47, 235142))
        m.write('00:23:4a:00:00:00', time=datetime(2020, 7, 31, 22, 5, 47, 235152))

        self.assertEqual(mock_write_api.write.call_count, 2)
        call_args_1 = mock_write_api.write.call_args_list[0][1]
        call_args_2 = mock_write_api.write.call_args_list[1][1]
        self.assertEqual(call_args_1['record']['time'], '2020-07-31T22:05:47.235142')
        self.assertEqual(call_args_2['record']['time'], '2020-07-31T22:05:47.235152')

if __name__ == '__main__':
    unittest.main()