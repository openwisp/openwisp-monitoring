"""
InfluxDB 2.x Database Client Tests
"""

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase, TransactionTestCase, tag
from django.utils.timezone import now
from freezegun import freeze_time
from swapper import load_model

from openwisp_monitoring.check import settings as check_settings
from openwisp_monitoring.check.tests import AutoDataCollectedCheck, AutoWifiClientCheck
from openwisp_monitoring.db.backends.influxdb2.client import (
    DatabaseClient,
    QueryResultSet,
)
from openwisp_monitoring.db.backends.influxdb2.queries import chart_query, summary_query
from openwisp_monitoring.device import tasks as device_tasks
from openwisp_monitoring.device.tests import TestDeviceMonitoringMixin
from openwisp_monitoring.device.utils import (
    DEFAULT_RP,
    SHORT_RP,
    manage_default_retention_policy,
    manage_short_retention_policy,
)
from openwisp_monitoring.monitoring import settings as monitoring_settings
from openwisp_monitoring.monitoring import tasks as monitoring_tasks
from openwisp_monitoring.monitoring.tests import (
    RequireTimeseriesBackendMixin,
    TestMonitoringMixin,
)
from openwisp_utils.tests import capture_stderr

from ... import device_data_query, timeseries_db
from ...exceptions import TimeseriesWriteException

Chart = load_model("monitoring", "Chart")
Check = load_model("check", "Check")
Device = load_model("config", "Device")
DeviceData = load_model("device_monitoring", "DeviceData")
Metric = load_model("monitoring", "Metric")
Notification = load_model("openwisp_notifications", "Notification")


@tag("timeseries_client", "influxdb2")
class TestInfluxDb2Client(RequireTimeseriesBackendMixin, TestCase):
    """Tests for InfluxDB 2.0 client."""

    expected_backend = "influxdb2"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.timeseries_db = DatabaseClient().attach_queries(timeseries_db.queries)
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

    def test_validate_query_aggregate_window(self):
        aggregate_queries = [
            'from(bucket: "test") |> aggregateWindow(every: 10m, fn: mean)',
            'from(bucket: "test") |> aggregateWindow(every: 10m, fn: sum)',
            'from(bucket: "test") |> aggregateWindow(every: 10m, fn: count)',
        ]
        for query in aggregate_queries:
            result = self.timeseries_db.validate_query(query)
            self.assertTrue(result, f"aggregateWindow query not detected: {query}")

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

    def test_format_flux_string_edge_cases(self):
        test_cases = [
            ("plain text", '"plain text"'),
            ('quote"slash\\', '"quote\\"slash\\\\"'),
            ("${name}", '"\\${name}"'),
            ("line1\nline2\ttab\rreturn", '"line1\\nline2\\ttab\\rreturn"'),
            ("café", '"café"'),
            ("\x01", '"\\x01"'),
            ("\x00\x1f\x7f", '"\\x00\\x1f\\x7f"'),
            ('café "${name}"\n\\', '"café \\"\\${name}\\"\\n\\\\"'),
        ]
        for value, expected in test_cases:
            with self.subTest(value=value):
                self.assertEqual(
                    self.timeseries_db._format_flux_string(value),
                    expected,
                )

    def test_write_single_point(self):
        """Test writing a single data point."""
        with patch.object(self.timeseries_db, "_write_api") as mock_write_api:
            self.timeseries_db.write(
                name="test_measurement",
                values={"field1": 10, "field2": 20},
                tags={"host": "localhost"},
            )
            mock_write_api.write.assert_called()
            call_args = mock_write_api.write.call_args
            record = call_args[1]["record"]
            self.assertEqual(record["measurement"], "test_measurement")
            self.assertEqual(record["fields"], {"field1": 10, "field2": 20})
            self.assertEqual(
                call_args[1]["bucket"], settings.TIMESERIES_DATABASE["NAME"]
            )

    def test_write_uses_retention_policy_bucket(self):
        """Test writing with a retention policy uses the mapped bucket."""
        with patch.object(self.timeseries_db, "_write_api") as mock_write_api:
            self.timeseries_db.write(
                name="test_measurement",
                values={"field1": 10},
                retention_policy=SHORT_RP,
            )
            call_args = mock_write_api.write.call_args
            self.assertEqual(
                call_args[1]["bucket"], f'{settings.TIMESERIES_DATABASE["NAME"]}_short'
            )

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

    def test_batch_write(self):
        """Test batch writing multiple data points."""
        with patch.object(self.timeseries_db, "_write_api") as mock_write_api:
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
            mock_write_api.write.assert_called()
            call_args = mock_write_api.write.call_args
            records = call_args[1]["record"]
            self.assertEqual(len(records), 2)
            self.assertEqual(records[0]["fields"]["field1"], 10)
            self.assertEqual(records[1]["fields"]["field1"], 20)

    def test_batch_write_groups_by_retention_policy_bucket(self):
        """Test batch writing separates default and short retention buckets."""
        with patch.object(self.timeseries_db, "_write_api") as mock_write_api:
            metric_data = [
                {
                    "name": "default_measurement",
                    "values": {"field1": 10},
                    "tags": {},
                },
                {
                    "name": "short_measurement",
                    "values": {"field1": 20},
                    "tags": {},
                    "retention_policy": SHORT_RP,
                },
            ]
            self.timeseries_db.batch_write(metric_data)

            calls = mock_write_api.write.call_args_list
            buckets = [call[1]["bucket"] for call in calls]
            self.assertEqual(
                buckets,
                [
                    settings.TIMESERIES_DATABASE["NAME"],
                    f'{settings.TIMESERIES_DATABASE["NAME"]}_short',
                ],
            )

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

    def test_query_does_not_catch_result_processing_errors(self):
        record = MagicMock()
        record.values = None
        table = MagicMock(records=[record])
        with patch.object(self.timeseries_db, "_query_api") as mock_query_api:
            mock_query_api.query.return_value = [table]
            with patch(
                "openwisp_monitoring.db.backends.influxdb2.client.logger.warning"
            ) as mocked_warning:
                with self.assertRaises(AttributeError):
                    self.timeseries_db.query('from(bucket: "openwisp2")')
        mocked_warning.assert_not_called()

    def test_query_result_set_iter_does_not_duplicate_points(self):
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
        iterated_points = list(resultset)
        self.assertEqual(len(iterated_points), 2)
        self.assertEqual(iterated_points, points)

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

    def test_read_escapes_flux_string_literals(self):
        with patch.object(
            self.timeseries_db, "query", return_value=QueryResultSet([])
        ) as mock_query:
            self.timeseries_db.read(
                key='cpu"main',
                fields=['usage"value'],
                tags={"host": 'server"1'},
                where=[('status"value', "=", 'warn"ing')],
            )
            flux_query = mock_query.call_args[0][0]
            self.assertIn(r'r._measurement == "cpu\"main"', flux_query)
            self.assertIn(r'r["host"] == "server\"1"', flux_query)
            self.assertIn(r'r._field == "usage\"value"', flux_query)
            self.assertIn(
                r'r._field == "status\"value" and r._value == "warn\"ing"',
                flux_query,
            )

    def test_read_uses_bracket_access_for_unsafe_tag_keys(self):
        with patch.object(
            self.timeseries_db, "query", return_value=QueryResultSet([])
        ) as mock_query:
            self.timeseries_db.read(
                key="cpu",
                fields=["usage"],
                tags={"client-id": 'server"1'},
            )
            flux_query = mock_query.call_args[0][0]
            self.assertIn(r'r["client-id"] == "server\"1"', flux_query)

    def test_read_rejects_none_tag_value(self):
        with self.assertRaises(self.timeseries_db.client_error) as context:
            self.timeseries_db.read(
                key="cpu",
                fields=["usage"],
                tags={"host": None},
            )
        self.assertEqual(
            str(context.exception), "None is not a valid Flux filter value"
        )

    def test_read_rejects_none_where_value(self):
        with self.assertRaises(self.timeseries_db.client_error) as context:
            self.timeseries_db.read(
                key="cpu",
                fields=["usage"],
                tags={},
                where=[("usage", "=", None)],
            )
        self.assertEqual(
            str(context.exception), "None is not a valid Flux filter value"
        )

    def test_read_escapes_mixed_flux_string_edge_cases(self):
        key = 'cpu${foo}"\\'
        field = "usage\n\t"
        host = 'server${1}"\\'
        note = "\x01"
        where_field = 'status${x}"\\'
        where_value = 'warn${y}"\\\n'
        with patch.object(
            self.timeseries_db, "query", return_value=QueryResultSet([])
        ) as mock_query:
            self.timeseries_db.read(
                key=key,
                fields=[field],
                tags={"host": host, "note": note},
                where=[(where_field, "=", where_value)],
            )
            flux_query = mock_query.call_args[0][0]
            self.assertIn(
                f"r._measurement == {self.timeseries_db._format_flux_string(key)}",
                flux_query,
            )
            self.assertIn(
                f"r._field == {self.timeseries_db._format_flux_string(field)}",
                flux_query,
            )
            self.assertIn(
                f'{self.timeseries_db._format_flux_property_access("host")} == '
                f"{self.timeseries_db._format_flux_string(host)}",
                flux_query,
            )
            self.assertIn(
                f'{self.timeseries_db._format_flux_property_access("note")} == '
                f"{self.timeseries_db._format_flux_string(note)}",
                flux_query,
            )
            self.assertIn(
                "r._field == "
                f"{self.timeseries_db._format_flux_string(where_field)} "
                f"and r._value == {self.timeseries_db._format_flux_string(where_value)}",
                flux_query,
            )

    def test_read_uses_retention_policy_bucket(self):
        """Test read() uses the mapped retention policy bucket."""
        with patch.object(
            self.timeseries_db, "query", return_value=QueryResultSet([])
        ) as mock_query:
            self.timeseries_db.read(
                key="cpu",
                fields=["usage"],
                tags={},
                retention_policy=SHORT_RP,
            )
            flux_query = mock_query.call_args[0][0]
            self.assertIn(
                f'from(bucket: "{settings.TIMESERIES_DATABASE["NAME"]}_short")',
                flux_query,
            )

    def test_delete_metric_data_all(self):
        """Test deleting all metric data."""
        with patch.object(self.timeseries_db, "_delete_api") as mock_delete_api:
            self.timeseries_db.delete_metric_data()
            self.assertEqual(mock_delete_api.delete.call_count, 2)
            calls = mock_delete_api.delete.call_args_list
            self.assertEqual(calls[0][0][2], "")
            self.assertEqual(calls[1][0][2], "")
            self.assertEqual(
                calls[0][1]["bucket"], settings.TIMESERIES_DATABASE["NAME"]
            )
            self.assertEqual(
                calls[1][1]["bucket"],
                f'{settings.TIMESERIES_DATABASE["NAME"]}_short',
            )

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

    def test_delete_metric_data_uses_fixed_future_stop(self):
        with patch.object(self.timeseries_db, "_delete_api") as mock_delete_api:
            self.timeseries_db.delete_metric_data(key="cpu")
            stop = mock_delete_api.delete.call_args[0][1]
            self.assertEqual(stop, datetime(2100, 1, 1, tzinfo=timezone.utc))

    def test_delete_metric_data_rejects_unsafe_tag_keys(self):
        with patch.object(self.timeseries_db, "_delete_api") as mock_delete_api:
            with self.assertRaises(ValueError):
                self.timeseries_db.delete_metric_data(tags={"host-name": "server1"})
        mock_delete_api.delete.assert_not_called()

    def test_delete_series_by_key(self):
        """Test InfluxDB 1.x compatible delete_series by measurement."""
        with patch.object(self.timeseries_db, "_delete_api") as mock_delete_api:
            self.timeseries_db.delete_series(key="cpu")
            self.assertEqual(mock_delete_api.delete.call_count, 2)
            call_args = mock_delete_api.delete.call_args_list[0]
            predicate = call_args[0][2]
            self.assertIn('_measurement="cpu"', predicate)

    def test_delete_metric_data_escapes_predicate_literals(self):
        with patch.object(self.timeseries_db, "_delete_api") as mock_delete_api:
            self.timeseries_db.delete_metric_data(
                key='cpu"main', tags={"host": 'server"1'}
            )
            predicate = mock_delete_api.delete.call_args[0][2]
            self.assertIn(r'_measurement="cpu\"main"', predicate)
            self.assertIn(r'host="server\"1"', predicate)

    @patch("openwisp_monitoring.utils.sleep")
    def test_delete_metric_data_surfaces_delete_failures(self, mocked_sleep):
        with patch.object(self.timeseries_db, "_delete_api") as mock_delete_api:
            mock_delete_api.delete.side_effect = self.timeseries_db.client_error(
                message="delete failed"
            )
            with self.assertRaises(self.timeseries_db.client_error):
                self.timeseries_db.delete_metric_data(key="cpu")
        mocked_sleep.assert_called()

    def test_delete_series_requires_filter(self):
        """Test delete_series rejects unfiltered deletes."""
        with patch.object(self.timeseries_db, "_delete_api") as mock_delete_api:
            with self.assertRaises(ValueError):
                self.timeseries_db.delete_series()
            mock_delete_api.delete.assert_not_called()

    @patch("openwisp_monitoring.utils.sleep")
    def test_delete_series_surfaces_delete_failures(self, mocked_sleep):
        with patch.object(self.timeseries_db, "_delete_api") as mock_delete_api:
            mock_delete_api.delete.side_effect = self.timeseries_db.client_error(
                message="delete failed"
            )
            with self.assertRaises(self.timeseries_db.client_error):
                self.timeseries_db.delete_series(key="cpu")
        mocked_sleep.assert_called()

    def test_get_top_fields(self):
        """Test top field selection uses summed field values."""
        query = self.timeseries_db.get_default_chart_query(has_object_scope=True)
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
                query=query,
                params={
                    "key": "applications",
                    "content_type": "test",
                    "object_id": "1",
                    "field_name": "app",
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

    def test_get_top_fields_supports_multi_value_scopes(self):
        with patch.object(
            self.timeseries_db, "query", return_value=QueryResultSet([])
        ) as mock_query:
            self.timeseries_db._get_top_fields(
                query=chart_query["general_traffic"]["influxdb2"],
                params={
                    "key": "traffic",
                    "organization_id": ["__all__", "org1", "org2"],
                    "location_id": ["loc1", "loc2"],
                    "floorplan_id": ["fp1", "fp2"],
                },
                chart_type="general_traffic",
                group_map={"30d": "30d"},
                number=2,
                time="30d",
            )
            flux_query = mock_query.call_args[0][0]
            self.assertIn(
                'contains(value: r.organization_id, set: ["org1", "org2"])',
                flux_query,
            )
            self.assertIn(
                'contains(value: r.location_id, set: ["loc1", "loc2"])',
                flux_query,
            )
            self.assertIn(
                'contains(value: r.floorplan_id, set: ["fp1", "fp2"])',
                flux_query,
            )
            self.assertNotIn("__all__", flux_query)

    def test_get_top_fields_empty_result(self):
        """Test top field selection returns empty list when no data is found."""
        query = self.timeseries_db.get_default_chart_query(has_object_scope=False)
        with patch.object(self.timeseries_db, "query", return_value=QueryResultSet([])):
            fields = self.timeseries_db._get_top_fields(
                query=query,
                params={"key": "applications", "field_name": "app"},
                chart_type="histogram",
                group_map={"30d": "30d"},
                number=3,
                time="30d",
            )
            self.assertEqual(fields, [])

    def test_get_top_fields_preserves_supplied_chart_query_semantics(self):
        result = QueryResultSet(
            [
                {
                    "_measurement": "cpu",
                    "_field": "CPU_load",
                    "_value": 75,
                    "time": "2024-03-25T12:00:00Z",
                }
            ]
        )
        with patch.object(
            self.timeseries_db, "query", return_value=result
        ) as mock_query:
            fields = self.timeseries_db._get_top_fields(
                query=chart_query["cpu"]["influxdb2"],
                params={
                    "key": "cpu",
                    "field_name": "cpu_usage",
                    "content_type": "config.device",
                    "object_id": "device-id",
                },
                chart_type="scatter",
                group_map={"1h": "5m"},
                number=1,
                time="1h",
            )
            self.assertEqual(fields, ["CPU_load"])
            flux_query = mock_query.call_args[0][0]
            self.assertIn('r._field == "cpu_usage"', flux_query)
            self.assertIn('map(fn: (r) => ({r with _field: "CPU_load"}))', flux_query)
            self.assertIn("|> mean()", flux_query)

    def test_get_list_retention_policies(self):
        """Test retrieving list of retention policies."""
        with patch.object(self.timeseries_db.db, "buckets_api") as mock_buckets_api:
            mock_api = MagicMock()
            mock_buckets_api.return_value = mock_api

            default_bucket = MagicMock()
            default_rule = MagicMock()
            default_rule.every_seconds = 94608000  # 3 years
            default_bucket.retention_rules = [default_rule]
            short_bucket = MagicMock()
            short_rule = MagicMock()
            short_rule.every_seconds = 86400  # 24 hours
            short_bucket.retention_rules = [short_rule]
            mock_api.find_bucket_by_name.side_effect = [default_bucket, short_bucket]
            policies = self.timeseries_db.get_list_retention_policies()
            self.assertEqual(len(policies), 2)
            self.assertEqual(policies[0]["name"], DEFAULT_RP)
            self.assertEqual(policies[0]["default"], True)
            self.assertEqual(policies[0]["duration"], "94608000s")
            self.assertEqual(policies[1]["name"], SHORT_RP)
            self.assertEqual(policies[1]["default"], False)
            self.assertEqual(policies[1]["duration"], "86400s")
            self.assertEqual(policies[0]["replication"], 1)

    def test_create_or_alter_retention_policy_creates_short_bucket(self):
        """Test short retention policy creates the mapped short bucket."""
        with patch.object(self.timeseries_db.db, "buckets_api") as mock_buckets_api:
            mock_api = MagicMock()
            mock_buckets_api.return_value = mock_api
            mock_api.find_bucket_by_name.return_value = None
            self.timeseries_db.create_or_alter_retention_policy(SHORT_RP, "24h0m0s")
            mock_api.create_bucket.assert_called_once()
            call_kwargs = mock_api.create_bucket.call_args[1]
            self.assertEqual(
                call_kwargs["bucket_name"],
                f'{settings.TIMESERIES_DATABASE["NAME"]}_short',
            )

    def test_create_or_alter_retention_policy_handles_missing_bucket_error(self):
        with patch.object(self.timeseries_db.db, "buckets_api") as mock_buckets_api:
            mock_api = MagicMock()
            mock_buckets_api.return_value = mock_api
            mock_api.find_bucket_by_name.side_effect = self.timeseries_db.client_error(
                message="could not find bucket"
            )
            self.timeseries_db.create_or_alter_retention_policy(SHORT_RP, "24h0m0s")
            mock_api.create_bucket.assert_called_once()

    @patch("openwisp_monitoring.utils.sleep")
    def test_create_or_alter_retention_policy_surfaces_lookup_failures(
        self, mocked_sleep
    ):
        with patch.object(self.timeseries_db.db, "buckets_api") as mock_buckets_api:
            mock_api = MagicMock()
            mock_buckets_api.return_value = mock_api
            mock_api.find_bucket_by_name.side_effect = self.timeseries_db.client_error(
                message="lookup failed"
            )
            with self.assertRaises(self.timeseries_db.client_error):
                self.timeseries_db.create_or_alter_retention_policy(SHORT_RP, "24h0m0s")
            mock_api.create_bucket.assert_not_called()
        mocked_sleep.assert_called()

    @patch("openwisp_monitoring.utils.sleep")
    def test_create_or_alter_retention_policy_surfaces_update_failures(
        self, mocked_sleep
    ):
        with patch.object(self.timeseries_db.db, "buckets_api") as mock_buckets_api:
            mock_api = MagicMock()
            mock_buckets_api.return_value = mock_api
            mock_bucket = MagicMock()
            mock_api.find_bucket_by_name.return_value = mock_bucket
            mock_api.update_bucket.side_effect = self.timeseries_db.client_error(
                message="update failed"
            )
            with self.assertRaises(self.timeseries_db.client_error):
                self.timeseries_db.create_or_alter_retention_policy(SHORT_RP, "24h0m0s")
            mock_api.create_bucket.assert_not_called()
        mocked_sleep.assert_called()

    def test_get_query_basic(self):
        """Test basic Flux query generation for charts."""
        query = self.timeseries_db.get_query(
            chart_type="line",
            params={"key": "cpu"},
            time="1h",
            group_map={"1h": "5m"},
        )
        self.assertIn('from(bucket: "', query)
        self.assertIn("range(start: -1h)", query)
        self.assertIn('_measurement == "cpu"', query)

    def test_get_query_keeps_chart_range_separate_from_window(self):
        query = self.timeseries_db.get_query(
            chart_type="scatter",
            params={
                "key": "cpu",
                "field_name": "cpu_usage",
                "content_type": "config.device",
                "object_id": "device-id",
            },
            time="1h",
            group_map={"1h": "5m"},
            query=chart_query["cpu"]["influxdb2"],
        )

        self.assertIn("range(start: -1h)", query)
        self.assertIn('aggregateWindow(every: 5m, fn: mean, timeSrc: "_start")', query)

    def test_query_bundle_matches_backend_contract(self):
        self.timeseries_db.queries.validate(self.timeseries_db.backend_name)
        for config in self.timeseries_db.queries.chart_query.values():
            self.assertIn("influxdb2", config)
            self.assertIn('from(bucket: "{bucket}")', config["influxdb2"])

    def test_get_query_uses_flux_chart_template(self):
        query = self.timeseries_db.get_query(
            chart_type="scatter",
            params={
                "key": "cpu",
                "field_name": "cpu_usage",
                "time": "2024-03-25 00:00:00",
                "end_date": "2024-03-26 00:00:00",
                "content_type": "config.device",
                "object_id": "device-id",
            },
            time="1d",
            group_map={"1d": "10m"},
            query=chart_query["cpu"]["influxdb2"],
            timezone="UTC",
        )
        self.assertIn(f'from(bucket: "{self.timeseries_db.db_name}")', query)
        self.assertIn('start: time(v: "2024-03-25T00:00:00Z")', query)
        self.assertIn('stop: time(v: "2024-03-26T00:00:00Z")', query)
        self.assertIn('r.content_type == "config.device"', query)
        self.assertIn('r.object_id == "device-id"', query)
        self.assertIn('r._field == "cpu_usage"', query)
        self.assertIn('aggregateWindow(every: 10m, fn: mean, timeSrc: "_start")', query)
        self.assertIn(
            "date.truncate(t: r._time, unit: 10m)",
            query,
        )
        self.assertIn('_field: "CPU_load"', query)

    def test_get_query_converts_naive_chart_range_from_timezone_to_utc(self):
        query = self.timeseries_db.get_query(
            chart_type="bar",
            params={
                "key": "ping",
                "field_name": "reachable",
                "time": "2024-03-25 10:00:00",
                "end_date": "2024-03-25 11:00:00",
                "content_type": "config.device",
                "object_id": "device-id",
            },
            time="1d",
            group_map={"1d": "10m"},
            query=chart_query["uptime"]["influxdb2"],
            timezone="Asia/Kolkata",
        )

        self.assertIn('start: time(v: "2024-03-25T04:30:00Z")', query)
        self.assertIn('stop: time(v: "2024-03-25T05:30:00Z")', query)

    def test_generated_query_converts_naive_chart_range_from_timezone_to_utc(self):
        query = self.timeseries_db.get_query(
            chart_type="line",
            params={
                "key": "cpu",
                "field_name": "cpu_usage",
                "time": "2024-03-25 10:00:00",
                "end_date": "2024-03-25 11:00:00",
            },
            time="1d",
            group_map={"1d": "10m"},
            timezone="Asia/Kolkata",
        )
        self.assertIn('range(start: time(v: "2024-03-25T04:30:00Z")', query)
        self.assertIn('stop: time(v: "2024-03-25T05:30:00Z"))', query)

    def test_get_query_escapes_default_chart_filters(self):
        query = self.timeseries_db.get_query(
            chart_type="line",
            params={
                "key": 'cpu"main',
                "content_type": 'config"device',
                "object_id": 'device"id',
            },
            time="1h",
            group_map={"1h": "5m"},
            fields=['usage"value'],
            query="".join(self.timeseries_db.queries.default_chart_query[0:2]),
        )
        self.assertIn(r'r._measurement == "cpu\"main"', query)
        self.assertIn(r'r.content_type == "config\"device"', query)
        self.assertIn(r'r.object_id == "device\"id"', query)
        self.assertIn(r'contains(value: r._field, set: ["usage\"value"])', query)

    def test_get_query_escapes_flux_chart_template_literals(self):
        query = self.timeseries_db.get_query(
            chart_type="scatter",
            params={
                "key": 'ping"main',
                "field_name": 'reachable"value',
                "time": "2024-03-25 00:00:00",
                "end_date": "2024-03-26 00:00:00",
                "content_type": 'config"device',
                "object_id": 'device"id',
            },
            time="1d",
            group_map={"1d": "10m"},
            query=chart_query["uptime"]["influxdb2"],
        )
        self.assertIn(r'r._measurement == "ping\"main"', query)
        self.assertIn(r'r.content_type == "config\"device"', query)
        self.assertIn(r'r.object_id == "device\"id"', query)
        self.assertIn(r'r._field == "reachable\"value"', query)

    def test_format_flux_time_date_only(self):
        self.assertEqual(
            self.timeseries_db._format_flux_time("2024-03-26"),
            'time(v: "2024-03-26T00:00:00Z")',
        )

    def test_get_open_range_stop_uses_fixed_future_datetime(self):
        self.assertEqual(
            self.timeseries_db._get_open_range_stop(),
            datetime(2100, 1, 1, tzinfo=timezone.utc),
        )

    def test_read_uses_fixed_future_stop_for_datetime_since(self):
        with patch.object(
            self.timeseries_db, "query", return_value=QueryResultSet([])
        ) as mock_query:
            self.timeseries_db.read(
                key="cpu",
                fields=["usage"],
                tags={},
                since=datetime(2000, 1, 1),
            )
            flux_query = mock_query.call_args[0][0]
            self.assertIn('stop: time(v: "2100-01-01T00:00:00+00:00")', flux_query)

    def test_get_query_summary_uses_whole_range_aggregate(self):
        query = self.timeseries_db.get_query(
            chart_type="scatter",
            params={
                "key": "cpu",
                "field_name": "cpu_usage",
                "time": "2024-03-25 00:00:00",
            },
            time="1d",
            group_map={"1d": "10m"},
            query=chart_query["cpu"]["influxdb2"],
            summary=True,
        )
        self.assertIn("|> mean()", query)
        self.assertNotIn("aggregateWindow", query)
        self.assertNotIn("date.truncate", query)
        self.assertNotIn('|> duplicate(column: "_start", as: "_time")', query)

    def test_get_query_chart_uses_window_start_as_time(self):
        query = self.timeseries_db.get_query(
            chart_type="bar",
            params={
                "key": "ping",
                "field_name": "reachable",
                "time": "2024-03-25 00:00:00",
            },
            time="1d",
            group_map={"1d": "10m"},
            query=chart_query["uptime"]["influxdb2"],
        )

        self.assertIn('aggregateWindow(every: 10m, fn: mean, timeSrc: "_start")', query)
        self.assertIn('timeSrc: "_start"', query)
        self.assertIn("date.truncate(t: r._time, unit: 10m)", query)

    def test_get_query_summary_uses_whole_range_wifi_clients_count(self):
        query = self.timeseries_db.get_query(
            chart_type="bar",
            params={
                "key": "wifi_clients",
                "field_name": "clients",
                "time": "2024-03-25 00:00:00",
            },
            time="1d",
            group_map={"1d": "1h"},
            query=chart_query["wifi_clients"]["influxdb2"],
            summary=True,
        )

        self.assertIn('|> unique(column: "_value")', query)
        self.assertIn("|> count()", query)
        self.assertNotIn("|> window(", query)
        self.assertNotIn('|> duplicate(column: "_start", as: "_time")', query)

    def test_built_in_chart_queries_have_explicit_summary_queries(self):
        self.assertEqual(set(chart_query.keys()), set(summary_query.keys()))

    def test_get_query_summary_does_not_rewrite_custom_flux_query(self):
        custom_query = (
            'from(bucket: "{bucket}") |> range(start: {time_start}{end_range})'
            ' |> filter(fn: (r) => r._measurement == "{key}")'
            " |> aggregateWindow(every: {window}, fn: mean)"
            ' |> map(fn: (r) => ({{r with _field: "custom_mean"}}))'
        )
        query = self.timeseries_db.get_query(
            chart_type="scatter",
            params={
                "key": "cpu",
                "time": "2024-03-25 00:00:00",
            },
            time="1d",
            group_map={"1d": "10m"},
            query=custom_query,
            summary=True,
        )
        self.assertIn("aggregateWindow(every: 10m, fn: mean)", query)
        self.assertIn('map(fn: (r) => ({r with _field: "custom_mean"}))', query)

    def test_device_data_query_uses_configured_bucket(self):
        query = device_data_query.format(SHORT_RP, "device_data", "device-id")
        self.assertIn(
            f'from(bucket: "{settings.TIMESERIES_DATABASE["NAME"]}_short")', query
        )
        self.assertNotIn(f'from(bucket: "{SHORT_RP}")', query)
        self.assertIn('r._measurement == "device_data"', query)
        self.assertIn('r.pk == "device-id"', query)

    def test_device_data_query_escapes_flux_string_literals(self):
        with patch.object(timeseries_db, "db_name", 'open"wisp\\bucket'):
            query = device_data_query.format(
                SHORT_RP,
                'device"data',
                'device\\id"',
            )
        self.assertIn('from(bucket: "open\\"wisp\\\\bucket_short")', query)
        self.assertIn('r._measurement == "device\\"data"', query)
        self.assertIn('r.pk == "device\\\\id\\""', query)

    def test_get_query_with_fields(self):
        """Test Flux query generation with field filtering."""
        query = self.timeseries_db.get_query(
            chart_type="line",
            params={"key": "cpu"},
            time="1h",
            group_map={"1h": "5m"},
            fields=["usage", "load"],
        )
        self.assertIn('contains(value: r._field, set: ["usage", "load"])', query)

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
        self.assertIn('contains(value: r._field, set: ["rx_bytes", "tx_bytes"])', query)
        self.assertIn("|> sum()", query)
        # Check for GB conversion (divide by 1e9)
        self.assertIn("float(v: r._value) / 1000000000.0", query)

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
        self.assertIn("float(v: r._value) / 1000000000.0", query)

    def test_get_query_general_traffic_supports_multi_value_scopes(self):
        query = self.timeseries_db.get_query(
            chart_type="general_traffic",
            params={
                "key": "traffic",
                "organization_id": ["__all__", "org1", "org2"],
                "location_id": ["loc1", "loc2"],
                "floorplan_id": ["fp1", "fp2"],
            },
            time="24h",
            group_map={"24h": "1d"},
            fields=["rx_bytes", "tx_bytes"],
        )
        self.assertIn(
            'contains(value: r.organization_id, set: ["org1", "org2"])',
            query,
        )
        self.assertIn('contains(value: r.location_id, set: ["loc1", "loc2"])', query)
        self.assertIn(
            'contains(value: r.floorplan_id, set: ["fp1", "fp2"])',
            query,
        )
        self.assertNotIn("__all__", query)

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
        self.assertIn('|> distinct(column: "_value")', query)
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
        self.assertIn('|> distinct(column: "_value")', query)
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
        self.assertIn(
            'contains(value: r._field, set: ["rtt_avg", "rtt_max", "rtt_min"])',
            query,
        )
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

    def test_get_list_query_backfills_missing_multifield_summary_values(self):
        query = (
            'from(bucket: "openwisp2")'
            " |> filter(fn: (r) => r._field =~ /^(signal_strength|signal_power)$/)"
        )
        result = QueryResultSet(
            [
                {
                    "_measurement": "signal",
                    "_field": "signal_power",
                    "_value": -70.0,
                    "time": "2024-03-25T12:00:00Z",
                }
            ]
        )
        with patch.object(self.timeseries_db, "query", return_value=result):
            points = self.timeseries_db.get_list_query(query)
        self.assertEqual(
            points,
            [
                {
                    "time": "2024-03-25T12:00:00Z",
                    "signal_power": -70.0,
                    "signal_strength": None,
                }
            ],
        )

    def test_get_list_query_backfills_missing_remapped_summary_values(self):
        query = (
            'from(bucket: "openwisp2")'
            " |> filter(fn: (r) => r._field =~ /^(signal_quality|snr)$/)"
            " |> map(fn: (r) => ({r with "
            '_field: if r._field == "snr" then "signal_to_noise_ratio" '
            'else "signal_quality"}))'
        )
        result = QueryResultSet(
            [
                {
                    "_measurement": "signal",
                    "_field": "signal_quality",
                    "_value": -7.0,
                    "time": "2024-03-25T12:00:00Z",
                }
            ]
        )

        with patch.object(self.timeseries_db, "query", return_value=result):
            points = self.timeseries_db.get_list_query(query)
        self.assertEqual(
            points,
            [
                {
                    "time": "2024-03-25T12:00:00Z",
                    "signal_quality": -7.0,
                    "signal_to_noise_ratio": None,
                }
            ],
        )


@tag("influxdb2")
class TestInfluxDb2UdpDelivery(
    RequireTimeseriesBackendMixin, TestMonitoringMixin, TestCase
):
    """Will fail if UDP is not working"""

    expected_backend = "influxdb2"

    def test_udp_write_reaches_influxdb2(self):
        if not timeseries_db.use_udp:
            self.skipTest(
                "Skipped InfluxDB 2.x UDP delivery test (not running in UDP mode)."
            )
        test_id = f"udp-delivery-{uuid4()}"
        timeseries_db.write(
            "udp_delivery_test", {"value": 42}, tags={"test_id": test_id}
        )
        points = []
        for _attempt in range(15):
            points = timeseries_db.read(
                "udp_delivery_test",
                "value",
                {"test_id": test_id},
                limit=1,
            )
            if points:
                break
            time.sleep(0.2)
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0]["value"], 42)


@tag("timeseries_client", "influxdb2")
class TestInfluxDb2ClientIntegration(
    RequireTimeseriesBackendMixin, TestMonitoringMixin, TestCase
):
    expected_backend = "influxdb2"

    @classmethod
    def setUpClass(cls):
        cls._require_timeseries_backend()
        cls._write_delay_patcher = patch.object(
            monitoring_tasks.timeseries_write,
            "delay",
            side_effect=monitoring_tasks.timeseries_write.run,
        )
        cls._batch_write_delay_patcher = patch.object(
            monitoring_tasks.timeseries_batch_write,
            "delay",
            side_effect=monitoring_tasks.timeseries_batch_write.run,
        )
        cls._device_write_delay_patcher = patch.object(
            device_tasks.write_device_metrics,
            "delay",
            side_effect=device_tasks.write_device_metrics.run,
        )
        started_patchers = []
        try:
            for patcher in (
                cls._write_delay_patcher,
                cls._batch_write_delay_patcher,
                cls._device_write_delay_patcher,
            ):
                patcher.start()
                started_patchers.append(patcher)
            super().setUpClass()
            manage_short_retention_policy()
        except Exception:
            for patcher in reversed(started_patchers):
                patcher.stop()
            raise
        assert settings.TIMESERIES_DATABASE["BACKEND"].endswith("influxdb2")

    @classmethod
    def tearDownClass(cls):
        cls._device_write_delay_patcher.stop()
        cls._batch_write_delay_patcher.stop()
        cls._write_delay_patcher.stop()
        super().tearDownClass()

    def test_metric_write_and_read_round_trip(self):
        metric = self._create_general_metric(name="load")
        self._write_metric(metric, 50, check=False)
        points = self._read_metric(metric)
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0][metric.field_name], 50)

    def test_metric_read_omit_since(self):
        """Metric.read() should not hide stored data older than 24 hours if ``since`` is omitted."""
        metric = self._create_general_metric(name="historical-load")
        metric.write(
            50,
            time=datetime(2024, 3, 25, 10, 0, tzinfo=timezone.utc),
            current=False,
        )
        points = self._read_metric(metric, limit=None)
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0][metric.field_name], 50)

    def test_metric_read_order_and_same_key_different_fields(self):
        metric = self._create_general_metric(name="load")
        self._write_metric(metric, 30, check=False)
        self._write_metric(metric, 40, check=False, time=now() - timedelta(hours=2))
        ascending = self._read_metric(metric, limit=2, order="time")
        descending = self._read_metric(metric, limit=2, order="-time")
        self.assertEqual([point["value"] for point in ascending], [40, 30])
        self.assertEqual([point["value"] for point in descending], [30, 40])
        download = self._create_general_metric(
            name="traffic (download)",
            key="traffic",
            field_name="download",
        )
        upload = self._create_general_metric(
            name="traffic (upload)",
            key="traffic",
            field_name="upload",
        )
        timestamp = now() - timedelta(hours=1)
        self._write_metric(download, 200, check=False, time=timestamp)
        self._write_metric(upload, 100, check=False, time=timestamp)
        self.assertEqual(self._read_metric(download, order="-time")[0]["download"], 200)
        self.assertEqual(self._read_metric(upload, order="-time")[0]["upload"], 100)

    def test_metric_read_limit_applies_to_latest_point_only(self):
        """limit=1 should return one latest point, not one row per Flux field."""
        metric = self._create_general_metric(
            name="optional-field-metric",
            configuration="test_alert_field",
        )
        old_time = now() - timedelta(hours=2)
        new_time = now() - timedelta(hours=1)
        metric.write(
            10,
            extra_values={"test_related_1": 100},
            time=old_time,
            check=False,
        )
        metric.write(20, time=new_time, check=False)
        points = self._read_metric(
            metric,
            limit=1,
            order="-time",
            extra_fields="*",
        )
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0][metric.field_name], 20)
        self.assertNotIn("test_related_1", points[0])

    def test_metric_batch_write_round_trip(self):
        metric = self._create_general_metric(name="batch-load")
        Metric.batch_write(
            [
                (
                    metric,
                    {
                        "value": 11,
                        "time": now() - timedelta(minutes=5),
                        "current": False,
                    },
                ),
                (
                    metric,
                    {
                        "value": 22,
                        "time": now(),
                        "current": False,
                    },
                ),
            ]
        )
        values = self._read_metric(metric, limit=2, order="time")
        self.assertEqual([point["value"] for point in values], [11, 22])

    @patch.object(monitoring_settings, "TOLERANCE_INTERVAL", 300)
    def test_alert_tolerance_uses_read_contract(self):
        self._create_admin()
        metric = self._create_general_metric(name="load")
        self._create_alert_settings(
            metric=metric,
            custom_operator=">",
            custom_threshold=90,
            custom_tolerance=5,
        )
        with freeze_time("2024-03-25 10:00:00"):
            metric.write(99)
        with freeze_time("2024-03-25 10:02:00"):
            metric.write(99)
        metric.refresh_from_db(fields=["is_healthy", "is_healthy_tolerant"])
        self.assertEqual(metric.is_healthy, False)
        self.assertEqual(metric.is_healthy_tolerant, True)
        self.assertEqual(Notification.objects.count(), 0)
        with freeze_time("2024-03-25 10:06:00"):
            metric.write(99)
        metric.refresh_from_db(fields=["is_healthy", "is_healthy_tolerant"])
        self.assertEqual(metric.is_healthy, False)
        self.assertEqual(metric.is_healthy_tolerant, False)
        self.assertEqual(Notification.objects.count(), 1)

    def test_chart_read_default_query_round_trip(self):
        chart = self._create_chart(configuration="dummy")
        data = self._read_chart(chart)
        self.assertIn("x", data)
        self.assertIn("traces", data)
        self.assertEqual(len(data["x"]), 3)
        self.assertEqual(data["traces"], [("value", [3, 6, 9])])
        self.assertEqual(data["summary"], {"value": None})

    def test_ping_uptime_chart_summary_round_trip(self):
        metric = self._create_object_metric(name="ping", configuration="ping")
        timestamp = now()
        metric.write(
            1,
            extra_values={"loss": 0, "rtt_min": 1.2, "rtt_avg": 2.4, "rtt_max": 3.6},
            time=timestamp - timedelta(days=2),
        )
        metric.write(
            1,
            extra_values={"loss": 0, "rtt_min": 1.1, "rtt_avg": 2.1, "rtt_max": 3.1},
            time=timestamp - timedelta(days=1),
        )
        metric.write(
            1,
            extra_values={"loss": 0, "rtt_min": 1.0, "rtt_avg": 2.0, "rtt_max": 3.0},
            time=timestamp,
        )
        chart = Chart(metric=metric, configuration="uptime")
        chart.full_clean()
        chart.save()
        data = self._read_chart(chart, time="7d")
        self.assertEqual(data["summary"], {"uptime": 100.0})

    def test_ping_uptime_chart_uses_uniform_10_minute_buckets_for_1d(self):
        metric = self._create_object_metric(name="ping", configuration="ping")
        base_time = now().replace(
            year=2024, month=3, day=25, hour=10, minute=5, second=0, microsecond=0
        )
        timestamps = [
            base_time - timedelta(minutes=30),
            base_time - timedelta(minutes=20),
            base_time - timedelta(minutes=10),
            base_time,
        ]
        for timestamp in timestamps:
            metric.write(
                1,
                extra_values={
                    "loss": 0,
                    "rtt_min": 1.0,
                    "rtt_avg": 2.0,
                    "rtt_max": 3.0,
                },
                time=timestamp,
            )
        chart = Chart(metric=metric, configuration="uptime")
        chart.full_clean()
        chart.save()
        data = self._read_chart(
            chart,
            time="1d",
            start_date="2024-03-24 10:07:00",
            end_date="2024-03-25 10:07:00",
            timezone="UTC",
        )
        non_null_points = [
            datetime.strptime(timestamp, "%Y-%m-%d %H:%M")
            for timestamp, value in zip(data["x"], data["traces"][0][1])
            if value is not None
        ]

        self.assertGreaterEqual(len(non_null_points), 1)
        self.assertTrue(all(point.minute % 10 == 0 for point in non_null_points))
        if len(non_null_points) > 1:
            self.assertEqual(
                {
                    int((current - previous).total_seconds())
                    for previous, current in zip(non_null_points, non_null_points[1:])
                },
                {600},
            )
        self.assertEqual(
            non_null_points[-1].strftime("%Y-%m-%d %H:%M"), "2024-03-25 10:00"
        )
        self.assertEqual(data["summary"], {"uptime": 100.0})

    def test_ping_uptime_chart_zoom_range_uses_request_timezone(self):
        metric = self._create_object_metric(name="ping", configuration="ping")
        metric.write(
            1,
            extra_values={"loss": 0, "rtt_min": 1.0, "rtt_avg": 2.0, "rtt_max": 3.0},
            time=datetime(2024, 3, 25, 4, 40, tzinfo=timezone.utc),
        )
        chart = Chart(metric=metric, configuration="uptime")
        chart.full_clean()
        chart.save()
        data = self._read_chart(
            chart,
            time="1d",
            start_date="2024-03-25 10:00:00",
            end_date="2024-03-25 11:00:00",
            timezone="Asia/Kolkata",
        )
        self.assertIn("x", data)
        self.assertTrue(data["traces"], data)
        self.assertEqual(data["traces"][0][0], "uptime")
        self.assertIn(100.0, data["traces"][0][1])
        self.assertEqual(data["summary"], {"uptime": 100.0})

    def test_ping_uptime_chart_daily_window_uses_request_timezone(self):
        """Daily buckets should align to the request timezone midnight."""
        metric = self._create_object_metric(name="ping", configuration="ping")
        metric.write(
            1,
            extra_values={"loss": 0, "rtt_min": 1.0, "rtt_avg": 2.0, "rtt_max": 3.0},
            time=datetime(2024, 3, 24, 20, 0, tzinfo=timezone.utc),
        )
        chart = Chart(metric=metric, configuration="uptime")
        chart.full_clean()
        chart.save()
        data = self._read_chart(
            chart,
            time="30d",
            start_date="2024-03-01 00:00:00",
            end_date="2024-03-31 23:59:59",
            timezone="Asia/Kolkata",
        )
        self.assertIn("x", data)
        self.assertTrue(data["traces"], data)
        non_null_points = [
            timestamp
            for timestamp, value in zip(data["x"], data["traces"][0][1])
            if value is not None
        ]
        self.assertEqual(non_null_points, ["2024-03-25 00:00"])

    def test_delete_metric_data_and_delete_series_round_trip(self):
        general_metric = self._create_general_metric(name="delete-general")
        object_metric = self._create_object_metric(name="delete-object")
        short_metric = self._create_general_metric(name="delete-short")
        self._write_metric(general_metric, 100, check=False)
        self._write_metric(object_metric, 50, check=False)
        self._write_metric(short_metric, 75, check=False, retention_policy=SHORT_RP)
        self.assertEqual(self._read_metric(general_metric)[0]["value"], 100)
        self.assertEqual(self._read_metric(object_metric)[0]["value"], 50)
        self.assertEqual(
            self._read_metric(short_metric, retention_policy=SHORT_RP)[0]["value"], 75
        )
        timeseries_db.delete_series(key=object_metric.key, tags=object_metric.tags)
        self.assertEqual(self._read_metric(object_metric), [])
        self.assertEqual(self._read_metric(general_metric)[0]["value"], 100)
        self.assertEqual(
            self._read_metric(short_metric, retention_policy=SHORT_RP)[0]["value"], 75
        )
        timeseries_db.delete_metric_data(key=general_metric.key)
        self.assertEqual(self._read_metric(general_metric), [])
        timeseries_db.delete_metric_data(key=short_metric.key)
        self.assertEqual(self._read_metric(short_metric, retention_policy=SHORT_RP), [])

    def test_delete_metric_data_without_filters_clears_default_and_short_buckets(self):
        general_metric = self._create_general_metric(name="delete-all-general")
        short_metric = self._create_general_metric(name="delete-all-short")
        self._write_metric(general_metric, 100, check=False)
        self._write_metric(short_metric, 75, check=False, retention_policy=SHORT_RP)
        self.assertEqual(self._read_metric(general_metric)[0]["value"], 100)
        self.assertEqual(
            self._read_metric(short_metric, retention_policy=SHORT_RP)[0]["value"], 75
        )
        timeseries_db.delete_metric_data()
        self.assertEqual(self._read_metric(general_metric), [])
        self.assertEqual(self._read_metric(short_metric, retention_policy=SHORT_RP), [])

    def test_retention_policy_utilities_match_current_backend_behavior(self):
        manage_default_retention_policy()
        manage_short_retention_policy()
        policies = timeseries_db.get_list_retention_policies()
        self.assertEqual(len(policies), 2)
        self.assertEqual(policies[0]["name"], DEFAULT_RP)
        self.assertEqual(policies[0]["default"], True)
        self.assertEqual(policies[1]["name"], SHORT_RP)
        self.assertEqual(policies[1]["default"], False)

    @capture_stderr()
    def test_write_failure_raises_timeseries_exception(self):
        with patch.object(timeseries_db, "_write_api") as mock_write_api:
            mock_write_api.write.side_effect = RuntimeError("write failed")
            with self.assertRaises(TimeseriesWriteException):
                timeseries_db.write("test_write", {"value": 1})


@tag("timeseries_client", "influxdb2")
class TestInfluxDb2CheckIntegration(
    RequireTimeseriesBackendMixin,
    AutoWifiClientCheck,
    AutoDataCollectedCheck,
    TestDeviceMonitoringMixin,
    TransactionTestCase,
):
    _WIFI_CLIENTS = check_settings.CHECK_CLASSES[3][0]
    _DATA_COLLECTED = check_settings.CHECK_CLASSES[4][0]
    expected_backend = "influxdb2"

    @classmethod
    def setUpClass(cls):
        cls._require_timeseries_backend()
        cls._write_delay_patcher = patch.object(
            monitoring_tasks.timeseries_write,
            "delay",
            side_effect=monitoring_tasks.timeseries_write.run,
        )
        cls._batch_write_delay_patcher = patch.object(
            monitoring_tasks.timeseries_batch_write,
            "delay",
            side_effect=monitoring_tasks.timeseries_batch_write.run,
        )
        started_patchers = []
        try:
            for patcher in (
                cls._write_delay_patcher,
                cls._batch_write_delay_patcher,
            ):
                patcher.start()
                started_patchers.append(patcher)
            super().setUpClass()
            manage_short_retention_policy()
        except Exception:
            for patcher in reversed(started_patchers):
                patcher.stop()
            raise
        assert settings.TIMESERIES_DATABASE["BACKEND"].endswith("influxdb2")

    @classmethod
    def tearDownClass(cls):
        cls._batch_write_delay_patcher.stop()
        cls._write_delay_patcher.stop()
        super().tearDownClass()

    def _create_device(self, monitoring_status="ok", *args, **kwargs):
        device = super()._create_device(*args, **kwargs)
        device.monitoring.status = monitoring_status
        device.monitoring.save()
        return device

    def test_wifi_clients_check_round_trip(self):
        device = self._create_device()
        device_data = DeviceData(pk=device.pk)
        device_data.data = {"interfaces": []}
        sample_data = self._data()
        sample_data.pop("resources")
        device_data.writer.write(sample_data, current=False)
        raw_metric = Metric.objects.filter(
            key="wifi_clients", object_id=device.pk
        ).first()
        self.assertIsNotNone(
            raw_metric,
            list(
                Metric.objects.filter(object_id=device.pk).values_list("key", flat=True)
            ),
        )
        self.assertGreaterEqual(len(self._read_metric(raw_metric, limit=None)), 1)
        check = Check.objects.get(
            name="WiFi Clients",
            check_type=self._WIFI_CLIENTS,
            content_type=ContentType.objects.get_for_model(Device),
            object_id=device.pk,
        )
        result = check.perform_check()
        self.assertEqual(result, {"wifi_clients_min": 3, "wifi_clients_max": 3})
        for key in ("wifi_clients_min", "wifi_clients_max"):
            metric = Metric.objects.get(key=key, object_id=device_data.id)
            points = self._read_metric(metric, limit=None)
            self.assertEqual(len(points), 1)
            self.assertEqual(points[0]["clients"], 3)

    def test_data_collected_check_round_trip(self):
        device = self._create_device()
        device_data = DeviceData(pk=device.pk)
        device_data.data = {"interfaces": []}
        sample_data = self._data()
        sample_data.pop("resources")
        device_data.writer.write(sample_data, current=False)
        cache.clear()
        self.assertGreater(len(DeviceData(pk=device.pk).data["interfaces"]), 0)
        passive_metric = device.monitoring.related_metrics.exclude(
            configuration__in=device.monitoring.get_active_metrics()
        ).first()
        self.assertIsNotNone(
            passive_metric,
            list(
                device.monitoring.related_metrics.values_list(
                    "configuration",
                    "key",
                )
            ),
        )
        self.assertGreaterEqual(len(self._read_metric(passive_metric, limit=None)), 1)
        check = Check.objects.create(
            name="Data Collected",
            check_type=self._DATA_COLLECTED,
            content_type=ContentType.objects.get_for_model(Device),
            object_id=device.pk,
        )
        result = check.perform_check()
        self.assertEqual(result, {"data_collected": 1})
        metric = Metric.objects.get(key="data_collected", object_id=device_data.id)
        points = self._read_metric(metric, retention_policy=SHORT_RP)
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0]["data_collected"], 1)
