"""
InfluxDB 2.x Database Client Tests
"""

import os
from datetime import datetime
from unittest import SkipTest
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import TestCase, tag

from openwisp_monitoring.db.backends.influxdb2.client import (
    DatabaseClient,
    QueryResultSet,
)


@tag("timeseries_client")
class TestInfluxDB2Client(TestCase):
    """Tests for InfluxDB 2.x client."""

    @classmethod
    def setUpClass(cls):
        if os.environ.get("TIMESERIES_BACKEND") != "influxdb2":
            raise SkipTest('Set TIMESERIES_BACKEND="influxdb2" to run InfluxDB2 tests.')
        super().setUpClass()
        cls.timeseries_db = DatabaseClient()
        assert settings.TIMESERIES_DATABASE["BACKEND"].endswith("influxdb2")
        assert cls.timeseries_db.backend_name == "influxdb2"

    def test_backend_name(self):
        self.assertEqual(self.timeseries_db.backend_name, "influxdb2")

    def test_forbidden_queries(self):
        """Test that forbidden words are rejected in Flux queries."""
        queries = [
            'drop(bucket: "openwisp2")',
            "delete data from measurement",
            "alter bucket settings",
            "into other_measurement",
        ]
        for q in queries:
            with self.assertRaises(ValidationError):
                self.timeseries_db.validate_query(q)

    def test_validate_query_allowed(self):
        """Test that valid Flux queries pass validation."""
        query = 'from(bucket: "openwisp2") |> range(start: -24h)'
        # Should not raise
        result = self.timeseries_db.validate_query(query)
        self.assertFalse(result)  # No aggregate functions

    def test_validate_query_aggregate(self):
        """Test detection of aggregate functions in Flux queries."""
        aggregate_queries = [
            'from(bucket: "test") |> mean()',
            'from(bucket: "test") |> sum()',
            'from(bucket: "test") |> count()',
            'from(bucket: "test") |> max()',
            'from(bucket: "test") |> min()',
            'from(bucket: "test") |> stddev()',
        ]
        for query in aggregate_queries:
            result = self.timeseries_db.validate_query(query)
            self.assertTrue(result, f"Query should be detected as aggregate: {query}")

    def test_duration_to_seconds(self):
        """Test duration string conversion to seconds."""
        test_cases = [
            ("30s", 30),
            ("5m", 300),
            ("2h", 7200),
            ("7d", 604800),
            ("1w", 604800),
        ]
        for duration_str, expected_seconds in test_cases:
            result = self.timeseries_db._duration_to_seconds(duration_str)
            self.assertEqual(result, expected_seconds)

    def test_timestamp_format_datetime(self):
        """Test ISO format timestamp generation from datetime."""
        dt = datetime(2024, 3, 25, 12, 30, 45)
        timestamp = self.timeseries_db._get_timestamp(dt)
        self.assertIsInstance(timestamp, str)
        self.assertIn("2024-03-25T12:30:45", timestamp)

    def test_timestamp_format_string(self):
        """Test timestamp passthrough for string input."""
        timestamp_str = "2024-03-25T12:30:45"
        result = self.timeseries_db._get_timestamp(timestamp_str)
        self.assertEqual(result, timestamp_str)

    @patch("openwisp_monitoring.db.backends.influxdb2.client.DatabaseClient._write_api")
    def test_write_single_point(self, mock_write_api):
        """Test writing a single data point."""
        mock_instance = MagicMock()
        mock_write_api.return_value = mock_instance
        self.timeseries_db._write_api = mock_instance

        self.timeseries_db.write(
            name="test_measurement",
            values={"field1": 10, "field2": 20},
            tags={"host": "localhost"},
        )

        # Verify write was called
        mock_instance.write.assert_called()
        call_args = mock_instance.write.call_args
        record = call_args[1]["record"]
        self.assertEqual(record["measurement"], "test_measurement")
        self.assertEqual(record["fields"], {"field1": 10, "field2": 20})

    def test_write_with_database_parameter_warning(self):
        """Test that database parameter triggers warning."""
        with patch(
            "openwisp_monitoring.db.backends.influxdb2.client.logger"
        ) as mock_logger:
            with patch.object(self.timeseries_db, "_write_api"):
                self.timeseries_db.write(
                    name="test",
                    values={"value": 1},
                    database="different_db",
                )
                # Should log warning about database parameter being ignored
                mock_logger.warning.assert_called()

    @patch("openwisp_monitoring.db.backends.influxdb2.client.DatabaseClient._write_api")
    def test_batch_write(self, mock_write_api):
        """Test batch writing multiple data points."""
        mock_instance = MagicMock()
        mock_write_api.return_value = mock_instance
        self.timeseries_db._write_api = mock_instance

        metric_data = [
            {
                "name": "test_measurement",
                "values": {"field1": 10},
                "tags": {"host": "localhost"},
            },
            {
                "name": "test_measurement",
                "values": {"field1": 20},
                "tags": {"host": "localhost"},
            },
        ]
        self.timeseries_db.batch_write(metric_data)
        mock_instance.write.assert_called()
        call_args = mock_instance.write.call_args
        records = call_args[1]["record"]
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["fields"]["field1"], 10)
        self.assertEqual(records[1]["fields"]["field1"], 20)

    def test_query_result_set_get_points(self):
        """Test QueryResultSet.get_points() generator."""
        points = [
            {
                "_measurement": "cpu",
                "_field": "usage",
                "_value": 50,
                "time": "2024-03-25T12:00:00Z",
                "host": "server1",
            },
            {
                "_measurement": "cpu",
                "_field": "usage",
                "_value": 55,
                "time": "2024-03-25T12:01:00Z",
                "host": "server1",
            },
        ]
        resultset = QueryResultSet(points)
        result_points = list(resultset.get_points())
        self.assertEqual(len(result_points), 2)
        self.assertEqual(result_points[0]["_value"], 50)

    def test_query_result_set_keys(self):
        """Test QueryResultSet.keys() returns (measurement, tags) tuples."""
        points = [
            {
                "_measurement": "cpu",
                "_field": "usage",
                "_value": 50,
                "time": "2024-03-25T12:00:00Z",
                "host": "server1",
            },
        ]
        resultset = QueryResultSet(points)
        keys = resultset.keys()
        self.assertEqual(len(keys), 1)
        measurement, tags = keys[0]
        self.assertEqual(measurement, "cpu")
        self.assertIn("host", tags)

    def test_query_result_set_get_points_filtered(self):
        """Test QueryResultSet.get_points() with filters."""
        points = [
            {
                "_measurement": "cpu",
                "_field": "usage",
                "_value": 50,
                "time": "2024-03-25T12:00:00Z",
                "host": "server1",
            },
            {
                "_measurement": "memory",
                "_field": "usage",
                "_value": 70,
                "time": "2024-03-25T12:00:00Z",
                "host": "server1",
            },
        ]
        resultset = QueryResultSet(points)
        cpu_points = list(resultset.get_points(measurement="cpu"))
        self.assertEqual(len(cpu_points), 1)
        self.assertEqual(cpu_points[0]["_measurement"], "cpu")

    def test_query_result_set_items(self):
        """Test QueryResultSet.items() returns (key, generator) tuples."""
        points = [
            {
                "_measurement": "cpu",
                "_field": "usage",
                "_value": 50,
                "time": "2024-03-25T12:00:00Z",
                "host": "server1",
            },
        ]
        resultset = QueryResultSet(points)
        items = resultset.items()
        self.assertEqual(len(items), 1)
        key, points_gen = items[0]
        self.assertEqual(key[0], "cpu")
        # Generator should be iterable
        generated_points = list(points_gen)
        self.assertEqual(len(generated_points), 1)

    def test_read_count_distinct_single_field(self):
        """Test read() supports COUNT(DISTINCT(field)) for wifi clients."""
        result = QueryResultSet(
            [
                {
                    "_measurement": "wifi_clients",
                    "_field": "clients",
                    "_value": 3,
                    "time": "2024-03-25T12:00:00Z",
                    "content_type": "test.device",
                    "object_id": "1",
                },
            ]
        )
        with patch.object(
            self.timeseries_db, "query", return_value=result
        ) as mock_query:
            values = self.timeseries_db.read(
                key="wifi_clients",
                fields=["clients"],
                distinct_fields=["clients"],
                count_fields=["clients"],
                tags={"content_type": "test.device", "object_id": "1"},
            )
            self.assertEqual(values[0]["count"], 3)
            flux_query = mock_query.call_args[0][0]
            self.assertIn('distinct(column: "_value")', flux_query)
            self.assertIn("|> count()", flux_query)

    def test_read_count_distinct_unsupported_shape(self):
        """Test read() still rejects unsupported distinct/count combinations."""
        with self.assertRaises(NotImplementedError):
            self.timeseries_db.read(
                key="wifi_clients",
                fields=["clients"],
                distinct_fields=["clients"],
                count_fields=[],
                tags={},
            )

    def test_read_supports_order_by_alias(self):
        """Test read() accepts order_by as an alias for order."""
        with patch.object(
            self.timeseries_db, "query", return_value=QueryResultSet([])
        ) as mock_query:
            self.timeseries_db.read(
                key="cpu",
                fields=["usage"],
                tags={},
                order_by="-time",
            )
            flux_query = mock_query.call_args[0][0]
            self.assertIn('|> sort(columns: ["_time"], desc: true)', flux_query)

    def test_read_supports_where_filters(self):
        """Test read() translates simple WHERE conditions into Flux filters."""
        with patch.object(
            self.timeseries_db, "query", return_value=QueryResultSet([])
        ) as mock_query:
            self.timeseries_db.read(
                key="cpu",
                fields=["usage"],
                tags={},
                where=[("usage", ">=", 80)],
            )
            flux_query = mock_query.call_args[0][0]
            self.assertIn('r._field == "usage" and r._value >= 80', flux_query)

    def test_read_supports_wildcard_fields(self):
        """Test read() treats '*' as all fields and skips field filtering."""
        with patch.object(
            self.timeseries_db, "query", return_value=QueryResultSet([])
        ) as mock_query:
            self.timeseries_db.read(
                key="cpu",
                fields="*",
                tags={},
            )
            flux_query = mock_query.call_args[0][0]
            self.assertNotIn('r._field == "*"', flux_query)

    def test_read_supports_multiple_measurements(self):
        """Test read() translates comma-separated measurements to Flux OR filter."""
        with patch.object(
            self.timeseries_db, "query", return_value=QueryResultSet([])
        ) as mock_query:
            self.timeseries_db.read(
                key="cpu,memory,disk",
                fields="*",
                tags={},
            )
            flux_query = mock_query.call_args[0][0]
            self.assertIn('r._measurement == "cpu" or', flux_query)
            self.assertIn('r._measurement == "memory" or', flux_query)
            self.assertIn('r._measurement == "disk"', flux_query)

    def test_read_accepts_retention_policy_with_warning(self):
        """Test read() accepts retention_policy and logs compatibility warning."""
        with patch.object(self.timeseries_db, "query", return_value=QueryResultSet([])):
            with patch(
                "openwisp_monitoring.db.backends.influxdb2.client.logger"
            ) as mock_logger:
                self.timeseries_db.read(
                    key="cpu",
                    fields=["usage"],
                    tags={},
                    retention_policy="short",
                )
                mock_logger.warning.assert_called()

    def test_delete_metric_data_all(self):
        """Test deleting all metric data."""
        with patch.object(self.timeseries_db, "_delete_api") as mock_delete_api:
            self.timeseries_db.delete_metric_data()
            # Should call delete with empty predicate
            mock_delete_api.delete.assert_called()
            call_args = mock_delete_api.delete.call_args
            predicate = call_args[0][2]  # 3rd positional arg is predicate
            self.assertEqual(predicate, "")

    def test_delete_metric_data_by_key(self):
        """Test deleting metric data by measurement key."""
        with patch.object(self.timeseries_db, "_delete_api") as mock_delete_api:
            self.timeseries_db.delete_metric_data(key="cpu")
            mock_delete_api.delete.assert_called()
            call_args = mock_delete_api.delete.call_args
            predicate = call_args[0][2]
            self.assertIn('_measurement="cpu"', predicate)

    def test_delete_metric_data_by_tags(self):
        """Test deleting metric data by tags."""
        with patch.object(self.timeseries_db, "_delete_api") as mock_delete_api:
            self.timeseries_db.delete_metric_data(tags={"host": "server1"})
            mock_delete_api.delete.assert_called()
            call_args = mock_delete_api.delete.call_args
            predicate = call_args[0][2]
            self.assertIn('host="server1"', predicate)

    def test_delete_series_by_key(self):
        """Test InfluxDB 1.x compatible delete_series by measurement."""
        with patch.object(self.timeseries_db, "_delete_api") as mock_delete_api:
            self.timeseries_db.delete_series(key="cpu")
            mock_delete_api.delete.assert_called()
            call_args = mock_delete_api.delete.call_args
            predicate = call_args[0][2]
            self.assertIn('_measurement="cpu"', predicate)

    def test_delete_series_requires_filter(self):
        """Test delete_series rejects unfiltered deletes."""
        with patch.object(self.timeseries_db, "_delete_api") as mock_delete_api:
            with self.assertRaises(ValueError):
                self.timeseries_db.delete_series()
            mock_delete_api.delete.assert_not_called()

    def test_get_top_fields(self):
        """Test top field selection uses summed field values."""
        result = QueryResultSet(
            [
                {
                    "_measurement": "applications",
                    "_field": "http2",
                    "_value": 100,
                    "time": "2024-03-25T12:00:00Z",
                },
                {
                    "_measurement": "applications",
                    "_field": "ssh",
                    "_value": 90,
                    "time": "2024-03-25T12:00:00Z",
                },
            ]
        )
        with patch.object(
            self.timeseries_db, "query", return_value=result
        ) as mock_query:
            fields = self.timeseries_db._get_top_fields(
                query="ignored",
                params={
                    "key": "applications",
                    "content_type": "test",
                    "object_id": "1",
                },
                chart_type="histogram",
                group_map={"30d": "30d"},
                number=2,
                time="30d",
            )
            self.assertEqual(fields, ["http2", "ssh"])
            flux_query = mock_query.call_args[0][0]
            self.assertIn('group(columns: ["_field"])', flux_query)
            self.assertIn("sum()", flux_query)
            self.assertIn("limit(n: 2)", flux_query)

    def test_get_top_fields_empty_result(self):
        """Test top field selection returns empty list when no data is found."""
        with patch.object(self.timeseries_db, "query", return_value=QueryResultSet([])):
            fields = self.timeseries_db._get_top_fields(
                query="ignored",
                params={"key": "applications"},
                chart_type="histogram",
                group_map={"30d": "30d"},
                number=3,
                time="30d",
            )
            self.assertEqual(fields, [])

    def test_get_list_retention_policies(self):
        """Test retrieving list of retention policies."""
        with patch.object(self.timeseries_db.db, "buckets_api") as mock_buckets_api:
            mock_api = MagicMock()
            mock_buckets_api.return_value = mock_api

            mock_bucket = MagicMock()
            mock_rule = MagicMock()
            mock_rule.every_seconds = 604800  # 7 days
            mock_bucket.retention_rules = [mock_rule]
            mock_api.find_bucket_by_name.return_value = mock_bucket
            policies = self.timeseries_db.get_list_retention_policies()
            self.assertEqual(len(policies), 1)
            self.assertEqual(policies[0]["duration"], "604800s")
            self.assertEqual(policies[0]["replication"], 1)

    def test_get_query_basic(self):
        """Test basic Flux query generation for charts."""
        query = self.timeseries_db.get_query(
            chart_type="line",
            params={"key": "cpu"},
            time="1h",
            group_map={"1h": "5m"},
        )
        self.assertIn('from(bucket: "', query)
        self.assertIn("range(start: -5m)", query)
        self.assertIn('_measurement == "cpu"', query)

    def test_get_query_with_fields(self):
        """Test Flux query generation with field filtering."""
        query = self.timeseries_db.get_query(
            chart_type="line",
            params={"key": "cpu"},
            time="1h",
            group_map={"1h": "5m"},
            fields=["usage", "load"],
        )
        self.assertIn('_field in ("usage", "load")', query)

    def test_get_query_with_summary(self):
        """Test Flux query generation with aggregation."""
        query = self.timeseries_db.get_query(
            chart_type="line",
            params={"key": "cpu"},
            time="1h",
            group_map={"1h": "5m"},
            summary=True,
        )
        self.assertIn("mean()", query)

    def test_get_query_traffic_gb_conversion(self):
        """Test Flux query for traffic with GB conversion (divide by 1e9)."""
        query = self.timeseries_db.get_query(
            chart_type="traffic",
            params={"key": "traffic", "ifname": "eth0"},
            time="24h",
            group_map={"24h": "1d"},
            fields=["rx_bytes", "tx_bytes"],
        )
        self.assertIn('_measurement == "traffic"', query)
        self.assertIn('ifname == "eth0"', query)
        self.assertIn('_field in ("rx_bytes", "tx_bytes")', query)
        self.assertIn("|> sum()", query)
        # Check for GB conversion (divide by 1e9)
        self.assertIn("_value / 1000000000", query)

    def test_get_query_general_traffic_gb_conversion(self):
        """Test Flux query for general traffic with GB conversion."""
        query = self.timeseries_db.get_query(
            chart_type="general_traffic",
            params={
                "key": "traffic",
                "organization_id": "org1",
                "location_id": "loc1",
                "floorplan_id": "fp1",
            },
            time="24h",
            group_map={"24h": "1d"},
            fields=["rx_bytes", "tx_bytes"],
        )
        self.assertIn('_measurement == "traffic"', query)
        self.assertIn('organization_id == "org1"', query)
        self.assertIn('location_id == "loc1"', query)
        self.assertIn('floorplan_id == "fp1"', query)
        self.assertIn("|> sum()", query)
        self.assertIn("_value / 1000000000", query)

    def test_get_query_wifi_clients_count_distinct(self):
        """Test Flux query for wifi_clients using distinct() + count()."""
        query = self.timeseries_db.get_query(
            chart_type="wifi_clients",
            params={"key": "wifi_clients", "ifname": "wlan0"},
            time="24h",
            group_map={"24h": "1d"},
        )
        self.assertIn('_measurement == "wifi_clients"', query)
        self.assertIn('ifname == "wlan0"', query)
        # Check for COUNT(DISTINCT) simulation: distinct() + count()
        self.assertIn('|> distinct(column: "clients")', query)
        self.assertIn("|> count()", query)

    def test_get_query_general_wifi_clients_count_distinct(self):
        """Test Flux query for general_wifi_clients with org/location filters."""
        query = self.timeseries_db.get_query(
            chart_type="general_wifi_clients",
            params={
                "key": "wifi_clients",
                "organization_id": "org1",
                "location_id": "loc1",
                "floorplan_id": "fp1",
            },
            time="24h",
            group_map={"24h": "1d"},
        )
        self.assertIn('_measurement == "wifi_clients"', query)
        self.assertIn('organization_id == "org1"', query)
        self.assertIn('location_id == "loc1"', query)
        self.assertIn('floorplan_id == "fp1"', query)
        # Check for COUNT(DISTINCT) simulation
        self.assertIn('|> distinct(column: "clients")', query)
        self.assertIn("|> count()", query)

    def test_get_query_rtt_multiple_fields(self):
        """Test Flux query for RTT with multiple field aggregations."""
        query = self.timeseries_db.get_query(
            chart_type="rtt",
            params={"key": "ping"},
            time="24h",
            group_map={"24h": "1d"},
            fields=["rtt_avg", "rtt_max", "rtt_min"],
        )
        self.assertIn('_measurement == "ping"', query)
        self.assertIn('_field in ("rtt_avg", "rtt_max", "rtt_min")', query)
        # RTT should have mean aggregation
        self.assertIn("|> mean()", query)

    def test_query_result_set_pivoting_multifield(self):
        """Test QueryResultSet pivoting for multi-field results like RTT."""
        # Simulating how Flux returns multi-field data after pivoting
        points = [
            {
                "_measurement": "ping",
                "_field": "rtt_avg",
                "_value": 25.5,
                "time": "2024-03-25T12:00:00Z",
                "host": "device1",
            },
            {
                "_measurement": "ping",
                "_field": "rtt_max",
                "_value": 35.2,
                "time": "2024-03-25T12:00:00Z",
                "host": "device1",
            },
            {
                "_measurement": "ping",
                "_field": "rtt_min",
                "_value": 20.1,
                "time": "2024-03-25T12:00:00Z",
                "host": "device1",
            },
        ]
        resultset = QueryResultSet(points)

        # Get all points for ping measurement
        ping_points = list(resultset.get_points(measurement="ping"))
        self.assertEqual(len(ping_points), 3)

        # Verify field values
        fields_found = {p["_field"]: p["_value"] for p in ping_points}
        self.assertEqual(fields_found["rtt_avg"], 25.5)
        self.assertEqual(fields_found["rtt_max"], 35.2)
        self.assertEqual(fields_found["rtt_min"], 20.1)
