"""
Elasticsearch Database Client Tests
"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, call, patch

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.test import TestCase, TransactionTestCase, tag
from django.urls import reverse
from django.utils.timezone import now
from freezegun import freeze_time
from swapper import load_model

from openwisp_monitoring.check import settings as check_settings
from openwisp_monitoring.check.tests import AutoDataCollectedCheck, AutoWifiClientCheck
from openwisp_monitoring.db.backends.elasticsearch.client import (
    DatabaseClient,
    QueryResultSet,
)
from openwisp_monitoring.db.backends.elasticsearch.queries import (
    ElasticsearchQuery,
    chart_query,
    summary_query,
)
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

from ... import timeseries_db
from ...exceptions import TimeseriesWriteException

Chart = load_model("monitoring", "Chart")
Check = load_model("check", "Check")
Device = load_model("config", "Device")
DeviceData = load_model("device_monitoring", "DeviceData")
Metric = load_model("monitoring", "Metric")
Notification = load_model("openwisp_notifications", "Notification")


def _search_response(*documents, aggregations=None):
    return {
        "hits": {
            "total": {"value": len(documents)},
            "hits": [{"_source": document} for document in documents],
        },
        "aggregations": aggregations or {},
    }


@tag("timeseries_client", "elasticsearch")
class TestElasticsearchClient(RequireTimeseriesBackendMixin, TestCase):
    expected_backend = "elasticsearch"
    base_config = {
        "BACKEND": "openwisp_monitoring.db.backends.elasticsearch",
        "NAME": "openwisp2",
        "URL": "http://localhost:9200",
    }

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        assert settings.TIMESERIES_DATABASE["BACKEND"].endswith("elasticsearch")

    def setUp(self):
        super().setUp()
        self.timeseries_db = DatabaseClient().attach_queries(timeseries_db.queries)

    def _mock_db(self):
        mock_db = MagicMock()
        self.timeseries_db.__dict__["db"] = mock_db
        return mock_db

    def test_backend_name(self):
        self.assertEqual(self.timeseries_db.backend_name, "elasticsearch")
        self.assertFalse(self.timeseries_db.use_udp)

    def test_normalize_chart_window(self):
        cases = (
            ("1d", {"1d": "10m"}, "10m"),
            (5, None, "5m"),
            (0, None, "1m"),
            ("5", None, "5m"),
            ("10m", None, "10m"),
        )
        for time_value, group_map, expected in cases:
            with self.subTest(time_value=time_value, group_map=group_map):
                self.assertEqual(
                    self.timeseries_db._normalize_chart_window(time_value, group_map),
                    expected,
                )

    def test_validate_settings_accepts_supported_connection_options(self):
        for config in (
            self.base_config,
            {
                **self.base_config,
                "URL": "",
                "HOST": "localhost",
                "PORT": "9200",
            },
            {**self.base_config, "URL": "", "CLOUD_ID": "cluster:cloud-id"},
        ):
            with self.subTest(config=config):
                self.assertEqual(DatabaseClient.validate_settings(config), config)

    def test_validate_settings_rejects_missing_connection_options(self):
        config = {
            "BACKEND": "openwisp_monitoring.db.backends.elasticsearch",
            "NAME": "openwisp2",
        }
        with self.assertRaisesMessage(
            ImproperlyConfigured,
            'Elasticsearch TIMESERIES_DATABASE must define "CLOUD_ID", "URL", or both "HOST" and "PORT".',
        ):
            DatabaseClient.validate_settings(config)

    def test_validate_settings_rejects_unsafe_data_stream_names(self):
        invalid_names = (
            "",
            "OpenWISP",
            "openwisp*",
            "-openwisp",
            ".",
            "a" * 256,
        )
        for name in invalid_names:
            with self.subTest(name=name), self.assertRaisesMessage(
                ImproperlyConfigured,
                '"NAME" must be a valid Elasticsearch data stream name.',
            ):
                DatabaseClient.validate_settings(
                    {
                        **self.base_config,
                        "NAME": name,
                    }
                )

    def test_validate_settings_rejects_invalid_advanced_options(self):
        invalid_settings = (
            ({"OPTIONS": []}, '"OPTIONS" must be a mapping.'),
            ({"VERIFY_CERTS": "false"}, '"VERIFY_CERTS" must be a boolean.'),
            (
                {"USER": "openwisp"},
                '"USER" and "PASSWORD" must be configured together.',
            ),
            (
                {"PASSWORD": "secret"},
                '"USER" and "PASSWORD" must be configured together.',
            ),
        )
        for invalid_setting, message in invalid_settings:
            with self.subTest(setting=invalid_setting), self.assertRaisesMessage(
                ImproperlyConfigured, message
            ):
                DatabaseClient.validate_settings(
                    {
                        **self.base_config,
                        **invalid_setting,
                    }
                )

    @patch.dict(
        "openwisp_monitoring.db.backends.elasticsearch.client.TIMESERIES_DB",
        {
            **base_config,
            "API_KEY": "api-key",
            "BEARER_AUTH": "bearer",
            "USER": "openwisp",
            "PASSWORD": "secret",
            "CA_CERTS": "/tmp/ca.pem",
            "SSL_ASSERT_FINGERPRINT": "fingerprint",
            "VERIFY_CERTS": False,
            "OPTIONS": {
                "http_compress": True,
                "request_timeout": 30,
                "max_retries": 2,
                "retry_on_timeout": True,
            },
        },
        clear=True,
    )
    @patch("openwisp_monitoring.db.backends.elasticsearch.client.Elasticsearch")
    def test_client_kwargs_use_api_key_first(self, mock_client):
        client = DatabaseClient()
        client.db
        mock_client.assert_called_once_with(
            hosts=["http://localhost:9200"],
            api_key="api-key",
            ca_certs="/tmp/ca.pem",
            ssl_assert_fingerprint="fingerprint",
            verify_certs=False,
            http_compress=True,
            request_timeout=30,
            max_retries=2,
            retry_on_timeout=True,
        )

    @patch.dict(
        "openwisp_monitoring.db.backends.elasticsearch.client.TIMESERIES_DB",
        {
            **base_config,
            "BEARER_AUTH": "bearer",
            "USER": "openwisp",
            "PASSWORD": "secret",
        },
        clear=True,
    )
    @patch("openwisp_monitoring.db.backends.elasticsearch.client.Elasticsearch")
    def test_client_kwargs_use_bearer_before_basic_auth(self, mock_client):
        client = DatabaseClient()
        client.db
        mock_client.assert_called_once_with(
            hosts=["http://localhost:9200"],
            bearer_auth="bearer",
        )

    @patch.dict(
        "openwisp_monitoring.db.backends.elasticsearch.client.TIMESERIES_DB",
        {
            **base_config,
            "URL": "",
            "CLOUD_ID": "cluster:cloud-id",
            "USER": "openwisp",
            "PASSWORD": "secret",
        },
        clear=True,
    )
    @patch("openwisp_monitoring.db.backends.elasticsearch.client.Elasticsearch")
    def test_client_kwargs_support_cloud_id_and_basic_auth(self, mock_client):
        client = DatabaseClient()
        client.db
        mock_client.assert_called_once_with(
            cloud_id="cluster:cloud-id",
            basic_auth=("openwisp", "secret"),
        )

    def test_reset_clears_cached_state(self):
        client = DatabaseClient(db_name="initial-db")
        client.__dict__["db"] = object()
        client.reset(db_name="reset-db")
        self.assertEqual(client.db_name, "reset-db")
        self.assertNotIn("db", client.__dict__)

    def test_build_index_template_uses_data_stream_settings(self):
        body = self.timeseries_db._build_index_template_body(SHORT_RP)
        self.assertEqual(body["index_patterns"], ["openwisp2-short"])
        settings_body = body["template"]["settings"]
        self.assertEqual(settings_body["index.lifecycle.name"], "openwisp2-short-ilm")
        self.assertNotIn("lifecycle", body["template"])
        self.assertNotIn("index.mode", settings_body)
        self.assertNotIn("index.look_ahead_time", settings_body)
        self.assertNotIn("index.look_back_time", settings_body)
        self.assertNotIn("index.routing_path", settings_body)
        mappings = body["template"]["mappings"]["properties"]
        self.assertEqual(mappings["@timestamp"], {"type": "date"})
        self.assertEqual(mappings["measurement"], {"type": "keyword"})
        self.assertNotIn("openwisp_series_id", mappings)
        self.assertNotIn("openwisp_doc_count", mappings)
        self.assertEqual(mappings["openwisp_write_sequence"]["type"], "long")

    def test_build_lifecycle_policy_bounds_rollover_age(self):
        short_policy = self.timeseries_db._build_lifecycle_policy("24h0m0s")
        default_policy = self.timeseries_db._build_lifecycle_policy("26280h0m0s")
        no_retention_policy = self.timeseries_db._build_lifecycle_policy()
        self.assertEqual(
            short_policy["phases"]["hot"]["actions"]["rollover"]["max_age"],
            "86400s",
        )
        self.assertEqual(
            default_policy["phases"]["hot"]["actions"]["rollover"]["max_age"],
            "2592000s",
        )
        self.assertEqual(
            no_retention_policy["phases"]["hot"]["actions"]["rollover"]["max_age"],
            "2592000s",
        )
        self.assertNotIn("delete", no_retention_policy["phases"])

    def test_elasticsearch_9_api_type_errors_are_not_masked(self):
        mock_db = self._mock_db()
        mock_db.ilm.put_lifecycle.side_effect = TypeError("invalid policy")
        with self.assertRaisesMessage(TypeError, "invalid policy"):
            self.timeseries_db._put_lifecycle_policy("policy", {"phases": {}})
        mock_db.ilm.put_lifecycle.assert_called_once_with(
            name="policy",
            policy={"phases": {}},
        )

        mock_db.indices.put_index_template.side_effect = TypeError(
            "invalid index template"
        )
        with self.assertRaisesMessage(TypeError, "invalid index template"):
            self.timeseries_db._put_index_template()
        self.assertEqual(mock_db.indices.put_index_template.call_count, 1)

    @patch.object(DatabaseClient, "_data_stream_exists", side_effect=[False, True])
    def test_ensure_data_stream_resources_creates_policy_template_and_stream(
        self, mock_exists
    ):
        mock_db = self._mock_db()
        self.timeseries_db._ensure_data_stream_resources(SHORT_RP, "24h0m0s")
        mock_db.ilm.put_lifecycle.assert_called_once()
        policy = mock_db.ilm.put_lifecycle.call_args.kwargs["policy"]
        self.assertEqual(policy["phases"]["delete"]["min_age"], "86400s")
        mock_db.indices.put_index_template.assert_called_once()
        mock_db.indices.create_data_stream.assert_called_once_with(
            name="openwisp2-short"
        )
        self.assertEqual(mock_exists.call_count, 1)

        self.timeseries_db._ensure_data_stream_resources(SHORT_RP, "24h0m0s")
        self.assertEqual(mock_db.ilm.put_lifecycle.call_count, 2)
        self.assertEqual(mock_db.indices.put_index_template.call_count, 2)
        self.assertEqual(mock_db.indices.create_data_stream.call_count, 1)
        self.assertEqual(mock_exists.call_count, 2)

    @patch.object(DatabaseClient, "_ensure_data_stream_resources")
    def test_create_database_ensures_default_stream(self, mock_ensure):
        self.timeseries_db.create_database()
        mock_ensure.assert_called_once_with()

    @patch.object(DatabaseClient, "_ensure_data_stream_resources")
    def test_create_or_alter_retention_policy_ensures_retention_stream(
        self, mock_ensure
    ):
        self.timeseries_db.create_or_alter_retention_policy(SHORT_RP, "24h0m0s")
        mock_ensure.assert_called_once_with(
            retention_policy=SHORT_RP,
            duration="24h0m0s",
        )

    @patch.object(DatabaseClient, "_ensure_data_stream_resources")
    def test_create_or_alter_retention_policy_validates_before_network_call(
        self, mock_ensure
    ):
        with self.assertRaisesMessage(ValueError, 'Invalid duration "one day"'):
            self.timeseries_db.create_or_alter_retention_policy(SHORT_RP, "one day")
        mock_ensure.assert_not_called()

    @patch.object(
        DatabaseClient,
        "_ensure_data_stream_resources",
        side_effect=[ConnectionError("temporary failure"), None],
    )
    def test_create_or_alter_retention_policy_retries_network_errors(self, mock_ensure):
        self.timeseries_db.create_or_alter_retention_policy(SHORT_RP, "24h0m0s")
        self.assertEqual(mock_ensure.call_count, 2)

    def test_get_list_retention_policies(self):
        mock_db = self._mock_db()
        mock_db.ilm.get_lifecycle.return_value = {
            "openwisp2-autogen-ilm": {
                "policy": {"phases": {"delete": {"min_age": "94608000s"}}}
            },
            "openwisp2-short-ilm": {
                "policy": {"phases": {"delete": {"min_age": "86400s"}}}
            },
            "another-project-autogen-ilm": {
                "policy": {"phases": {"delete": {"min_age": "60s"}}}
            },
        }
        policies = self.timeseries_db.get_list_retention_policies()
        self.assertEqual(
            policies,
            [
                {
                    "name": DEFAULT_RP,
                    "default": True,
                    "duration": "94608000s",
                    "replication": 1,
                },
                {
                    "name": SHORT_RP,
                    "default": False,
                    "duration": "86400s",
                    "replication": 1,
                },
            ],
        )
        mock_db.ilm.get_lifecycle.assert_called_once_with(name="openwisp2-*-ilm")

    def test_get_data_stream_names_filters_namespace(self):
        mock_db = self._mock_db()
        mock_db.indices.get_data_stream.return_value = {
            "data_streams": [
                {"name": "openwisp2"},
                {"name": "openwisp2-short"},
                {"name": "openwisp2_test"},
                {"name": "openwisp20"},
            ]
        }
        self.assertEqual(
            self.timeseries_db._get_data_stream_names(),
            ["openwisp2", "openwisp2-short"],
        )

    def test_get_index_names_filters_data_stream_backing_indices(self):
        mock_db = self._mock_db()
        mock_db.indices.get.return_value = {
            "openwisp2": {},
            "openwisp2-short": {},
            "openwisp2_test": {},
            ".ds-openwisp2-2026.07.27-000001": {},
        }
        self.assertEqual(
            self.timeseries_db._get_index_names(), ["openwisp2", "openwisp2-short"]
        )

    @patch.object(DatabaseClient, "_delete_lifecycle_policies")
    @patch.object(DatabaseClient, "_delete_index_templates")
    @patch.object(DatabaseClient, "_get_data_stream_names", return_value=[])
    def test_drop_database_deletes_regular_namespace_indices(
        self, mock_streams, mock_templates, mock_policies
    ):
        mock_db = self._mock_db()
        mock_db.indices.get.return_value = {
            "openwisp2": {},
            "openwisp2-short": {},
            ".ds-openwisp2-2026.07.27-000001": {},
        }
        self.timeseries_db.drop_database()
        self.assertEqual(
            mock_db.indices.delete.call_args_list,
            [
                call(index="openwisp2"),
                call(index="openwisp2-short"),
            ],
        )
        mock_streams.assert_called_once()
        mock_templates.assert_called_once()
        mock_policies.assert_called_once()

    def test_drop_database_deletes_only_namespaced_resources(self):
        mock_db = self._mock_db()
        mock_db.indices.get_data_stream.return_value = {
            "data_streams": [
                {"name": "openwisp2"},
                {"name": "openwisp2-short"},
                {"name": "another-project"},
            ]
        }
        mock_db.indices.get.return_value = {
            "openwisp2-legacy": {},
            "another-project": {},
        }
        mock_db.ilm.get_lifecycle.return_value = {
            "openwisp2-autogen-ilm": {},
            "openwisp2-short-ilm": {},
            "another-project-autogen-ilm": {},
        }
        self.timeseries_db.drop_database()
        self.assertEqual(
            mock_db.indices.delete_data_stream.call_args_list,
            [
                call(name="openwisp2"),
                call(name="openwisp2-short"),
            ],
        )
        mock_db.indices.delete.assert_called_once_with(index="openwisp2-legacy")
        self.assertEqual(
            mock_db.indices.delete_index_template.call_args_list,
            [
                call(name="openwisp2-template"),
                call(name="openwisp2-*-template"),
            ],
        )
        mock_db.indices.get_index_template.assert_not_called()
        self.assertEqual(
            mock_db.ilm.delete_lifecycle.call_args_list,
            [
                call(name="openwisp2-autogen-ilm"),
                call(name="openwisp2-short-ilm"),
            ],
        )

    @patch.object(DatabaseClient, "_is_not_found")
    @patch.object(DatabaseClient, "_delete_lifecycle_policies")
    @patch.object(DatabaseClient, "_delete_index_templates")
    @patch.object(DatabaseClient, "_delete_indices")
    @patch.object(
        DatabaseClient,
        "_get_data_stream_names",
        return_value=["openwisp2", "openwisp2-short"],
    )
    def test_drop_database_retries_safely_after_partial_deletion(
        self,
        mock_streams,
        mock_indices,
        mock_templates,
        mock_policies,
        mock_is_not_found,
    ):
        mock_db = self._mock_db()
        transient_error = RuntimeError("temporary failure")
        missing_error = RuntimeError("already deleted")
        mock_db.indices.delete_data_stream.side_effect = [
            None,
            transient_error,
            missing_error,
            None,
        ]
        mock_is_not_found.side_effect = lambda exception: exception is missing_error
        self.timeseries_db.drop_database()
        self.assertEqual(mock_streams.call_count, 2)
        self.assertEqual(
            mock_db.indices.delete_data_stream.call_args_list,
            [
                call(name="openwisp2"),
                call(name="openwisp2-short"),
                call(name="openwisp2"),
                call(name="openwisp2-short"),
            ],
        )
        mock_indices.assert_called_once()
        mock_templates.assert_called_once()
        mock_policies.assert_called_once()

    def test_retention_policy_rejects_unsafe_stream_name(self):
        with self.assertRaisesMessage(
            ValueError,
            'Invalid Elasticsearch data stream name "openwisp2-other*"',
        ):
            self.timeseries_db.create_or_alter_retention_policy(
                "other*",
                "24h0m0s",
            )

    @patch.object(DatabaseClient, "_is_resource_exists", return_value=True)
    @patch.object(DatabaseClient, "_data_stream_exists", side_effect=[False, False])
    def test_ensure_data_stream_resources_raises_for_regular_index_collision(
        self, mock_exists, mock_resource_exists
    ):
        mock_db = self._mock_db()
        mock_db.indices.create_data_stream.side_effect = RuntimeError("name collision")
        with self.assertRaisesMessage(RuntimeError, "name collision"):
            self.timeseries_db._ensure_data_stream_resources()
        self.assertEqual(mock_exists.call_count, 2)
        mock_resource_exists.assert_called_once()

    @patch.object(DatabaseClient, "_ensure_data_stream_resources")
    def test_write_single_point(self, mock_ensure):
        mock_db = self._mock_db()
        timestamp = datetime(2024, 3, 25, 12, 0, tzinfo=timezone.utc)
        self.timeseries_db.write(
            "cpu",
            {"usage": 10},
            tags={"host": "server1"},
            timestamp=timestamp,
        )
        mock_ensure.assert_not_called()
        mock_db.index.assert_called_once_with(
            index="openwisp2",
            document={
                "@timestamp": "2024-03-25T12:00:00Z",
                "measurement": "cpu",
                "openwisp_write_sequence": 0,
                "tags": {"host": "server1"},
                "fields": {"usage": 10},
            },
            op_type="create",
            refresh="wait_for",
        )

    @patch.object(DatabaseClient, "_ensure_data_stream_resources")
    def test_write_preserves_zero_timestamp(self, mock_ensure):
        mock_db = self._mock_db()
        self.timeseries_db.write("cpu", {"usage": 10}, timestamp=0)
        mock_ensure.assert_not_called()
        self.assertEqual(mock_db.index.call_args.kwargs["document"]["@timestamp"], 0)

    @patch.object(DatabaseClient, "_ensure_data_stream_resources")
    @patch("openwisp_monitoring.db.backends.elasticsearch.client.bulk")
    def test_batch_write_builds_bulk_actions_without_stream_setup(
        self, mock_bulk, mock_ensure
    ):
        mock_db = self._mock_db()
        timestamp = datetime(2024, 3, 25, 12, 0, tzinfo=timezone.utc)
        self.timeseries_db.batch_write(
            [
                {
                    "name": "cpu",
                    "values": {"usage": 10},
                    "tags": {"host": "server1"},
                    "timestamp": timestamp,
                },
                {
                    "name": "memory",
                    "values": {"used": 20},
                    "tags": {"host": "server1"},
                    "timestamp": timestamp,
                    "retention_policy": SHORT_RP,
                },
                {
                    "name": "disk",
                    "values": {"used": 30},
                    "tags": {"host": "server1"},
                    "timestamp": timestamp,
                    "retention_policy": SHORT_RP,
                },
            ]
        )
        mock_ensure.assert_not_called()
        actions = mock_bulk.call_args.args[1]
        self.assertEqual(actions[0]["_op_type"], "create")
        self.assertEqual(actions[0]["_index"], "openwisp2")
        self.assertEqual(actions[1]["_index"], "openwisp2-short")
        self.assertEqual(actions[2]["_source"]["fields"], {"used": 30})
        mock_bulk.assert_called_once_with(mock_db, actions, refresh="wait_for")

    @patch.object(DatabaseClient, "_ensure_data_stream_resources")
    @patch("openwisp_monitoring.db.backends.elasticsearch.client.logger.warning")
    @patch("openwisp_monitoring.db.backends.elasticsearch.client.bulk")
    def test_batch_write_warns_once_per_distinct_database(
        self, mock_bulk, mocked_warning, mock_ensure
    ):
        self._mock_db()
        self.timeseries_db.batch_write(
            [
                {"name": "cpu", "values": {"usage": 10}, "database": "other"},
                {"name": "memory", "values": {"used": 20}, "database": "other"},
            ]
        )
        mocked_warning.assert_called_once()
        mock_ensure.assert_not_called()

    @patch.object(DatabaseClient, "_ensure_data_stream_resources")
    def test_write_failure_raises_timeseries_exception(self, mock_ensure):
        mock_db = self._mock_db()
        mock_db.index.side_effect = RuntimeError("write failed")
        with self.assertRaises(TimeseriesWriteException):
            self.timeseries_db.write("cpu", {"usage": 10})
        mock_ensure.assert_not_called()

    def test_query_result_set_get_points_keys_and_items(self):
        resultset = QueryResultSet(
            _search_response(
                {
                    "@timestamp": "2024-03-25T12:00:00Z",
                    "measurement": "cpu",
                    "tags": {"host": "server1"},
                    "fields": {"usage": 10, "load": 2},
                },
                {
                    "@timestamp": "2024-03-25T12:05:00Z",
                    "measurement": "memory",
                    "tags": {"host": "server2"},
                    "fields": {"used": 20},
                },
            )
        )
        self.assertEqual(len(resultset), 2)
        self.assertEqual(
            resultset.keys(),
            [
                ("cpu", {"host": "server1"}),
                ("memory", {"host": "server2"}),
            ],
        )
        cpu_points = list(resultset.get_points(measurement="cpu"))
        self.assertEqual(len(cpu_points), 2)
        self.assertEqual({point["_field"] for point in cpu_points}, {"usage", "load"})
        items = resultset.items()
        self.assertEqual(items[0][0], ("cpu", {"host": "server1"}))
        self.assertEqual(list(items[0][1]), cpu_points)

    def test_query_result_set_precision(self):
        response = _search_response(
            {
                "@timestamp": "2024-03-25T12:00:00Z",
                "measurement": "cpu",
                "fields": {"usage": 10},
            }
        )
        self.assertEqual(
            list(QueryResultSet(response, precision="ms").get_points())[0]["time"],
            1711368000000,
        )
        self.assertEqual(
            list(QueryResultSet(response, precision=None).get_points())[0]["time"],
            "2024-03-25T12:00:00Z",
        )

    def test_query_strips_internal_metadata(self):
        mock_db = self._mock_db()
        mock_db.search.return_value = _search_response()
        result = self.timeseries_db.query(
            {
                "__index": "openwisp2-short",
                "__openwisp_query_type": "chart",
                "query": {"match_all": {}},
            }
        )
        self.assertIsInstance(result, QueryResultSet)
        mock_db.search.assert_called_once_with(
            index="openwisp2-short",
            body={"query": {"match_all": {}}},
        )

    @patch.object(
        DatabaseClient, "query", return_value=QueryResultSet(_search_response())
    )
    def test_read_builds_search_body(self, mock_query):
        since = datetime(2024, 3, 25, 10, 0, tzinfo=timezone.utc)
        self.timeseries_db.read(
            key="cpu,memory",
            fields=["usage"],
            tags={"host": "server1"},
            since=since,
            where=[("usage", ">=", 80)],
            order_by="-time",
            limit=5,
            retention_policy=SHORT_RP,
        )
        query = mock_query.call_args.args[0]
        self.assertEqual(query["size"], 10000)
        self.assertEqual(
            query["sort"],
            [
                {"@timestamp": {"order": "desc"}},
                {"openwisp_write_sequence": {"order": "asc", "unmapped_type": "long"}},
            ],
        )
        self.assertEqual(query["__retention_policy"], SHORT_RP)
        filters = query["query"]["bool"]["filter"]
        self.assertIn({"terms": {"measurement": ["cpu", "memory"]}}, filters)
        self.assertIn({"term": {"tags.host": "server1"}}, filters)
        self.assertIn({"exists": {"field": "fields.usage"}}, filters)
        self.assertIn(
            {"range": {"@timestamp": {"gte": "2024-03-25T10:00:00Z"}}},
            filters,
        )

    @patch.object(DatabaseClient, "query")
    def test_read_returns_selected_fields(self, mock_query):
        mock_query.return_value = QueryResultSet(
            _search_response(
                {
                    "@timestamp": "2024-03-25T12:00:00Z",
                    "measurement": "cpu",
                    "tags": {"host": "server1"},
                    "fields": {"usage": 10, "load": 2},
                }
            )
        )
        points = self.timeseries_db.read("cpu", "usage", {"host": "server1"})
        self.assertEqual(points, [{"time": 1711368000, "usage": 10}])

    @patch.object(DatabaseClient, "query")
    def test_read_filters_by_unselected_field(self, mock_query):
        mock_query.return_value = QueryResultSet(
            _search_response(
                {
                    "@timestamp": "2024-03-25T12:00:00Z",
                    "measurement": "load",
                    "fields": {"value": 10, "related": 100},
                }
            )
        )
        points = self.timeseries_db.read(
            "load",
            "value",
            {},
            where=[("related", ">", 50)],
        )
        self.assertEqual(points, [{"time": 1711368000, "value": 10}])

    @patch.object(DatabaseClient, "query")
    def test_read_deduplicates_same_timestamp_before_where_filtering(self, mock_query):
        mock_query.return_value = QueryResultSet(
            _search_response(
                {
                    "@timestamp": "2024-03-25T12:00:00Z",
                    "measurement": "ping",
                    "tags": {"object_id": "1"},
                    "fields": {"reachable": 0},
                },
                {
                    "@timestamp": "2024-03-25T12:00:00Z",
                    "measurement": "ping",
                    "tags": {"object_id": "1"},
                    "fields": {"reachable": 1},
                },
            )
        )
        points = self.timeseries_db.read(
            "ping",
            "reachable",
            {"object_id": "1"},
            where=[("reachable", "<", 1)],
        )
        self.assertEqual(points, [])

    @patch.object(DatabaseClient, "query")
    def test_read_supports_wildcard_extra_fields(self, mock_query):
        mock_query.return_value = QueryResultSet(
            _search_response(
                {
                    "@timestamp": "2024-03-25T12:00:00Z",
                    "measurement": "cpu",
                    "fields": {"usage": 10, "load": 2},
                }
            )
        )
        points = self.timeseries_db.read("cpu", "usage", {}, extra_fields="*")
        self.assertEqual(points, [{"time": 1711368000, "usage": 10, "load": 2}])

    @patch.object(DatabaseClient, "query")
    def test_read_count_distinct_single_field(self, mock_query):
        mock_query.return_value = QueryResultSet(
            {"hits": {"hits": []}, "aggregations": {"count": {"value": 3}}}
        )
        points = self.timeseries_db.read(
            "wifi_clients",
            ["clients"],
            {"content_type": "config.device"},
            distinct_fields=["clients"],
            count_fields=["clients"],
        )
        self.assertEqual(points, [{"count": 3, "time": None}])
        query = mock_query.call_args.args[0]
        self.assertEqual(
            query["aggs"],
            {"count": {"cardinality": {"field": "fields.clients"}}},
        )

    def test_read_count_distinct_unsupported_shape(self):
        with self.assertRaises(NotImplementedError):
            self.timeseries_db.read(
                "wifi_clients",
                ["clients"],
                {},
                distinct_fields=["clients"],
                count_fields=[],
            )

    def test_get_query_builds_aggregate_chart_query(self):
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
            query=chart_query["uptime"]["elasticsearch"],
            timezone="Asia/Kolkata",
        )
        self.assertEqual(query["__index"], "openwisp2")
        self.assertEqual(query["__openwisp_query_type"], "chart")
        self.assertEqual(
            query["aggs"]["timeseries"]["date_histogram"],
            {
                "field": "@timestamp",
                "fixed_interval": "10m",
                "min_doc_count": 0,
                "extended_bounds": {
                    "min": "2024-03-25T04:30:00Z",
                    "max": "2024-03-25T05:30:00Z",
                },
                "time_zone": "Asia/Kolkata",
            },
        )
        filters = query["query"]["bool"]["filter"]
        self.assertIn(
            {
                "range": {
                    "@timestamp": {
                        "gte": "2024-03-25T04:30:00Z",
                        "lte": "2024-03-25T05:30:00Z",
                    }
                }
            },
            filters,
        )
        self.assertEqual(
            query["aggs"]["timeseries"]["aggs"]["uptime"],
            {
                "filter": {"exists": {"field": "fields.reachable"}},
                "aggs": {"value": {"avg": {"field": "fields.reachable"}}},
            },
        )
        self.assertEqual(query["__openwisp_metrics"][0]["scale"], 100)

    def test_build_metric_aggregation(self):
        cases = (
            ("avg", {"avg": {"field": "fields.value"}}),
            ("sum", {"sum": {"field": "fields.value"}}),
            (
                "cardinality",
                {"cardinality": {"field": "fields.value"}},
            ),
            ("mode", {"terms": {"field": "fields.value", "size": 1}}),
            ("unknown", {"avg": {"field": "fields.value"}}),
        )
        for aggregation, expected in cases:
            with self.subTest(aggregation=aggregation):
                result = self.timeseries_db._build_metric_aggregation(
                    {"field": "value", "agg": aggregation}
                )
                self.assertEqual(result["aggs"]["value"], expected)

    def test_get_query_builds_summary_query(self):
        query = self.timeseries_db.get_query(
            chart_type="traffic",
            params={"key": "traffic", "retention_policy": SHORT_RP},
            time="1d",
            group_map={"1d": "10m"},
            query=chart_query["traffic"]["elasticsearch"],
            summary=True,
        )
        self.assertEqual(query["__index"], "openwisp2-short")
        self.assertNotIn("timeseries", query["aggs"])
        self.assertEqual(
            query["aggs"]["upload"],
            {
                "filter": {"exists": {"field": "fields.tx_bytes"}},
                "aggs": {"value": {"sum": {"field": "fields.tx_bytes"}}},
            },
        )
        self.assertEqual(
            query["aggs"]["download"],
            {
                "filter": {"exists": {"field": "fields.rx_bytes"}},
                "aggs": {"value": {"sum": {"field": "fields.rx_bytes"}}},
            },
        )

    def test_get_query_builds_raw_chart_query(self):
        query = self.timeseries_db.get_query(
            chart_type="line",
            params={"key": "cpu", "field_name": "usage"},
            time="1h",
            group_map={"1h": "5m"},
            fields=["usage", "load"],
        )
        self.assertEqual(query["__openwisp_query_type"], "raw_chart")
        self.assertEqual(query["__openwisp_fields"], ["usage", "load"])
        self.assertEqual(query["sort"], [{"@timestamp": {"order": "asc"}}])
        self.assertEqual(
            query["query"]["bool"]["filter"][-1],
            {
                "bool": {
                    "should": [
                        {"exists": {"field": "fields.usage"}},
                        {"exists": {"field": "fields.load"}},
                    ],
                    "minimum_should_match": 1,
                }
            },
        )

    def test_query_bundle_matches_backend_contract(self):
        self.timeseries_db.queries.validate(self.timeseries_db.backend_name)
        self.assertEqual(set(chart_query.keys()), set(summary_query.keys()))
        for key, config in self.timeseries_db.queries.chart_query.items():
            self.assertIn("elasticsearch", config)
            self.assertEqual(
                summary_query[key]["elasticsearch"], config["elasticsearch"]
            )
            self.assertIsNot(
                summary_query[key]["elasticsearch"], config["elasticsearch"]
            )

    @patch.object(
        ElasticsearchQuery,
        "resolve",
        autospec=True,
        wraps=ElasticsearchQuery.resolve,
    )
    def test_default_chart_query_omits_unused_filter_metadata(self, mock_resolve):
        default_query = self.timeseries_db.queries.default_chart_query
        self.assertIsInstance(default_query, ElasticsearchQuery)
        query = self.timeseries_db.get_default_chart_query(has_object_scope=True)
        mock_resolve.assert_called_once_with(default_query)
        self.assertNotIn("filters", query)
        self.assertIsNot(query, default_query)

    @patch.object(DatabaseClient, "query")
    def test_get_top_fields(self, mock_query):
        mock_query.return_value = QueryResultSet(
            {
                "aggregations": {
                    "top_fields": {
                        "value": {
                            "http2": 101,
                            "ssh": 90,
                            "udp": 80,
                            "is_bool": True,
                            "ignored": "string",
                        }
                    }
                }
            }
        )
        fields = self.timeseries_db._get_top_fields(
            query=self.timeseries_db.get_default_chart_query(has_object_scope=False),
            params={"key": "applications", "field_name": "app"},
            chart_type="histogram",
            group_map={"30d": "30d"},
            number=2,
            time="30d",
        )
        self.assertEqual(fields, ["http2", "ssh"])
        search = mock_query.call_args.args[0]
        self.assertEqual(search["size"], 0)
        self.assertNotIn("_source", search)
        self.assertIn("scripted_metric", search["aggs"]["top_fields"])

    @patch.object(DatabaseClient, "query")
    def test_get_list_query_converts_chart_aggregations(self, mock_query):
        query = self.timeseries_db.get_query(
            chart_type="bar",
            params={"key": "ping", "field_name": "reachable"},
            time="1d",
            group_map={"1d": "10m"},
            query=chart_query["uptime"]["elasticsearch"],
        )
        mock_query.return_value = QueryResultSet(
            {
                "hits": {"hits": []},
                "aggregations": {
                    "timeseries": {
                        "buckets": [
                            {
                                "key": 1711368000000,
                                "uptime": {"value": 0.5},
                            }
                        ]
                    }
                },
            }
        )
        self.assertEqual(
            self.timeseries_db.get_list_query(query),
            [{"time": 1711368000, "uptime": 50.0}],
        )

    @patch.object(DatabaseClient, "query")
    def test_get_list_query_omits_empty_chart_aggregations(self, mock_query):
        query = self.timeseries_db.get_query(
            chart_type="bar",
            params={"key": "ping", "field_name": "reachable"},
            time="1d",
            group_map={"1d": "10m"},
            query=chart_query["uptime"]["elasticsearch"],
        )
        mock_query.return_value = QueryResultSet(
            {
                "hits": {"hits": []},
                "aggregations": {
                    "timeseries": {
                        "buckets": [
                            {
                                "key": 1711368000000,
                                "doc_count": 0,
                                "uptime": {"value": None},
                            }
                        ]
                    }
                },
            }
        )
        self.assertEqual(self.timeseries_db.get_list_query(query), [])

    @patch.object(DatabaseClient, "query")
    def test_get_list_query_omits_empty_chart_summary(self, mock_query):
        query = self.timeseries_db.get_query(
            chart_type="bar",
            params={"key": "ping", "field_name": "reachable"},
            time="1d",
            group_map={"1d": "10m"},
            summary=True,
            query=chart_query["uptime"]["elasticsearch"],
        )
        mock_query.return_value = QueryResultSet(
            {
                "hits": {"hits": []},
                "aggregations": {"uptime": {"value": None}},
            }
        )
        self.assertEqual(self.timeseries_db.get_list_query(query), [])

    def test_grouped_chart_truncation_logs_once(self):
        query = {
            "__openwisp_metric": {"name": "value", "field": "clients"},
            "__openwisp_group_by": "organization_id",
            "__openwisp_summary": False,
        }
        response = {
            "aggregations": {
                "timeseries": {
                    "buckets": [
                        {
                            "key": 1711368000000,
                            "groups": {
                                "sum_other_doc_count": 2,
                                "buckets": [
                                    {
                                        "key": "org-1",
                                        "value": {"value": 3},
                                    }
                                ],
                            },
                        },
                        {
                            "key": 1711368600000,
                            "groups": {
                                "sum_other_doc_count": 4,
                                "buckets": [
                                    {
                                        "key": "org-1",
                                        "value": {"value": 5},
                                    }
                                ],
                            },
                        },
                    ]
                }
            }
        }
        with self.assertLogs(
            "openwisp_monitoring.db.backends.elasticsearch.client",
            level="WARNING",
        ) as captured:
            points = self.timeseries_db._get_grouped_chart_points(response, query)
        self.assertEqual(
            points,
            [
                {"time": 1711368000, "org-1": 3},
                {"time": 1711368600, "org-1": 5},
            ],
        )
        self.assertEqual(len(captured.output), 1)
        self.assertIn('tag "organization_id"', captured.output[0])
        self.assertIn("6 document(s)", captured.output[0])

    @patch.object(DatabaseClient, "query")
    def test_get_list_query_converts_raw_hits(self, mock_query):
        query = self.timeseries_db.get_query(
            chart_type="line",
            params={"key": "cpu", "field_name": "usage"},
            time="1h",
            group_map={"1h": "5m"},
        )
        mock_query.return_value = QueryResultSet(
            _search_response(
                {
                    "@timestamp": "2024-03-25T12:00:00Z",
                    "measurement": "cpu",
                    "tags": {"host": "server1"},
                    "fields": {"usage": 10, "load": 2},
                }
            )
        )
        self.assertEqual(
            self.timeseries_db.get_list_query(query),
            [{"time": 1711368000, "usage": 10}],
        )

    @patch.object(DatabaseClient, "query")
    def test_get_list_query_merges_raw_hits_by_time(self, mock_query):
        query = self.timeseries_db.get_query(
            chart_type="line",
            params={"key": "traffic", "field_name": "download"},
            time="1h",
            group_map={"1h": "5m"},
            fields=["download", "upload"],
        )
        mock_query.return_value = QueryResultSet(
            _search_response(
                {
                    "@timestamp": "2024-03-25T12:00:00Z",
                    "measurement": "traffic",
                    "fields": {"download": 10},
                },
                {
                    "@timestamp": "2024-03-25T12:00:00Z",
                    "measurement": "traffic",
                    "fields": {"upload": 20},
                },
            )
        )
        self.assertEqual(
            self.timeseries_db.get_list_query(query),
            [{"time": 1711368000, "download": 10, "upload": 20}],
        )

    @patch.object(DatabaseClient, "read", return_value=[{"time": 1, "data": {}}])
    def test_get_device_data_query_is_consumed_by_get_list_query(self, mock_read):
        query = self.timeseries_db.get_device_data_query(SHORT_RP, "device_data", "1")
        self.assertEqual(
            query,
            {
                "__openwisp_query_type": "device_data",
                "retention_policy": SHORT_RP,
                "measurement": "device_data",
                "pk": "1",
            },
        )
        self.assertEqual(
            self.timeseries_db.get_list_query(query), [{"time": 1, "data": {}}]
        )
        mock_read.assert_called_once_with(
            key="device_data",
            fields="data",
            tags={"pk": "1"},
            retention_policy=SHORT_RP,
            limit=1,
            order="-time",
            precision="s",
        )

    def test_validate_query_rejects_non_mapping(self):
        with self.assertRaises(ValidationError) as context:
            self.timeseries_db.validate_query("BAD")
        self.assertIn("configuration", context.exception.message_dict)

    def test_validate_query_uses_elasticsearch_validate_api(self):
        mock_db = self._mock_db()
        mock_db.indices.validate_query.return_value = {"valid": True}
        aggregate = self.timeseries_db.validate_query(
            {
                "query": {"match_all": {}},
                "aggs": {"usage": {"avg": {"field": "fields.usage"}}},
            }
        )
        self.assertTrue(aggregate)
        mock_db.indices.validate_query.assert_called_once_with(
            index="openwisp2",
            body={"query": {"match_all": {}}},
            explain=True,
        )

    def test_validate_query_raises_validation_error_for_invalid_query(self):
        mock_db = self._mock_db()
        mock_db.indices.validate_query.return_value = {
            "valid": False,
            "error": "bad query",
        }
        with self.assertRaises(ValidationError) as context:
            self.timeseries_db.validate_query({"query": {"bad": {}}})
        self.assertIn("bad query", context.exception.message_dict["configuration"])

    @patch.object(
        DatabaseClient,
        "_get_data_stream_names",
        return_value=["openwisp2", "openwisp2-short"],
    )
    @patch.object(DatabaseClient, "_get_index_names", return_value=[])
    def test_delete_metric_data_calls_delete_by_query_for_streams(
        self, mock_indices, mock_streams
    ):
        mock_db = self._mock_db()
        self.timeseries_db.delete_metric_data(
            key="cpu",
            tags={"host": "server1"},
        )
        self.assertEqual(mock_db.delete_by_query.call_count, 2)
        first_call = mock_db.delete_by_query.call_args_list[0]
        self.assertEqual(first_call.kwargs["index"], "openwisp2")
        filters = first_call.kwargs["body"]["query"]["bool"]["filter"]
        self.assertIn({"term": {"measurement": "cpu"}}, filters)
        self.assertIn({"term": {"tags.host": "server1"}}, filters)
        self.assertTrue(first_call.kwargs["refresh"])
        mock_indices.assert_called_once()

    @patch.object(DatabaseClient, "_get_data_stream_names")
    @patch.object(DatabaseClient, "_get_index_names")
    def test_delete_series_requires_filter(self, mock_indices, mock_streams):
        with self.assertRaises(ValueError):
            self.timeseries_db.delete_series()
        mock_streams.assert_not_called()
        mock_indices.assert_not_called()


class ElasticsearchIntegrationMixin:
    @classmethod
    def _get_class_patchers(cls):
        return (
            patch.object(
                monitoring_tasks.timeseries_write,
                "delay",
                side_effect=monitoring_tasks.timeseries_write.run,
            ),
            patch.object(
                monitoring_tasks.timeseries_batch_write,
                "delay",
                side_effect=monitoring_tasks.timeseries_batch_write.run,
            ),
        )

    @classmethod
    def setUpClass(cls):
        cls._class_patchers = cls._get_class_patchers()
        started_patchers = []
        super_setup_completed = False
        try:
            for patcher in cls._class_patchers:
                patcher.start()
                started_patchers.append(patcher)
            super().setUpClass()
            super_setup_completed = True
            manage_short_retention_policy()
        except Exception:
            for patcher in reversed(started_patchers):
                patcher.stop()
            if super_setup_completed:
                super().tearDownClass()
            raise
        assert settings.TIMESERIES_DATABASE["BACKEND"].endswith("elasticsearch")

    @classmethod
    def tearDownClass(cls):
        for patcher in reversed(cls._class_patchers):
            patcher.stop()
        super().tearDownClass()


@tag("timeseries_client", "elasticsearch")
class TestElasticsearchClientIntegration(
    ElasticsearchIntegrationMixin,
    RequireTimeseriesBackendMixin,
    TestMonitoringMixin,
    TestCase,
):
    expected_backend = "elasticsearch"

    @classmethod
    def _get_class_patchers(cls):
        return super()._get_class_patchers() + (
            patch.object(
                device_tasks.write_device_metrics,
                "delay",
                side_effect=device_tasks.write_device_metrics.run,
            ),
        )

    def test_metric_write_and_read_round_trip(self):
        metric = self._create_general_metric(name="load")
        self._write_metric(metric, 50, check=False)
        points = self._read_metric(metric)
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0][metric.field_name], 50)

    def test_large_device_data_snapshot_round_trip(self):
        device_id = "large-device-data"
        snapshot = json.dumps({"payload": "x" * 9000})
        timeseries_db.write(
            "device_data",
            {"data": snapshot},
            tags={"pk": device_id},
            retention_policy=SHORT_RP,
        )
        query = timeseries_db.get_device_data_query(
            SHORT_RP,
            "device_data",
            device_id,
        )
        points = timeseries_db.get_list_query(query, precision=None)
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0]["data"], snapshot)

    def test_metric_read_omit_since(self):
        metric = self._create_general_metric(name="historical-load")
        metric.write(50, time=now() - timedelta(days=2), current=False)
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
        base_time = now().replace(second=0, microsecond=0)
        with freeze_time(base_time):
            metric.write(99)
        with freeze_time(base_time + timedelta(minutes=2)):
            metric.write(99)
        metric.refresh_from_db(fields=["is_healthy", "is_healthy_tolerant"])
        self.assertEqual(metric.is_healthy, False)
        self.assertEqual(metric.is_healthy_tolerant, True)
        self.assertEqual(Notification.objects.count(), 0)
        with freeze_time(base_time + timedelta(minutes=6)):
            metric.write(99)
        metric.refresh_from_db(fields=["is_healthy", "is_healthy_tolerant"])
        self.assertEqual(metric.is_healthy, False)
        self.assertEqual(metric.is_healthy_tolerant, False)
        self.assertEqual(Notification.objects.count(), 1)

    @patch.object(monitoring_settings, "TOLERANCE_INTERVAL", 60)
    def test_alert_tolerance_uses_unselected_related_field(self):
        self._create_admin()
        metric = self._create_general_metric(configuration="test_alert_field")
        self._create_alert_settings(
            metric=metric,
            custom_operator=">",
            custom_threshold=30,
            custom_tolerance=1,
        )
        base_time = now().replace(second=0, microsecond=0)
        with freeze_time(base_time):
            metric.write(10, extra_values={"test_related_2": 35})
        metric.refresh_from_db(fields=["is_healthy", "is_healthy_tolerant"])
        self.assertEqual(metric.is_healthy, False)
        self.assertEqual(metric.is_healthy_tolerant, True)
        self.assertEqual(Notification.objects.count(), 0)
        with freeze_time(base_time + timedelta(seconds=61)):
            metric.write(10, extra_values={"test_related_2": 35})
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

    def test_chart_top_fields_round_trip(self):
        metric = self._create_object_metric(
            name="applications",
            configuration="get_top_fields",
        )
        chart = Chart(metric=metric, configuration="histogram")
        self.assertEqual(chart.get_top_fields(number=3), [])
        metric.write(
            None,
            extra_values={
                "http2": 100,
                "ssh": 90,
                "udp": 80,
                "spdy": 70,
            },
        )
        self.assertEqual(chart.get_top_fields(number=3), ["http2", "ssh", "udp"])

    def test_chart_top_fields_aggregates_all_documents(self):
        metric = self._create_object_metric(
            name="top-fields-all-documents",
            configuration="get_top_fields",
        )
        chart = Chart(metric=metric, configuration="histogram")
        metric.write(None, extra_values={"http2": 100, "ssh": 0})
        metric.write(None, extra_values={"http2": 0, "ssh": 200})
        self.assertEqual(chart.get_top_fields(number=1), ["ssh"])

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

    def test_chart_summary_does_not_sum_split_tag_series(self):
        metric = self._create_object_metric(name="disk", configuration="disk")
        timestamp = now()
        timeseries_db.write(
            metric.key,
            {metric.field_name: 75},
            tags=metric.tags,
            timestamp=timestamp - timedelta(days=2),
        )
        tags = {**metric.tags, "host": "openwisp-staging"}
        timeseries_db.write(
            metric.key,
            {metric.field_name: 76},
            tags=tags,
            timestamp=timestamp,
        )
        chart = Chart(metric=metric, configuration="disk")
        chart.full_clean()
        chart.save()
        data = self._read_chart(chart, time="7d")
        self.assertEqual(data["summary"], {"disk_usage": 75.5})

    def test_chart_read_does_not_hide_split_tag_series(self):
        metric = self._create_object_metric(name="disk", configuration="disk")
        timestamp = now()
        timeseries_db.write(
            metric.key,
            {metric.field_name: 75},
            tags=metric.tags,
            timestamp=timestamp - timedelta(days=2),
        )
        tags = {**metric.tags, "host": "openwisp-staging"}
        timeseries_db.write(
            metric.key,
            {metric.field_name: 76},
            tags=tags,
            timestamp=timestamp,
        )
        chart = Chart(metric=metric, configuration="disk")
        chart.full_clean()
        chart.save()
        data = self._read_chart(chart, time="7d")
        values = [value for value in data["traces"][0][1] if value is not None]
        self.assertEqual(values, [75.0, 76.0])

    def test_ping_uptime_chart_uses_uniform_10_minute_buckets_for_1d(self):
        metric = self._create_object_metric(name="ping", configuration="ping")
        base_time = (
            (now() - timedelta(days=1))
            .astimezone(timezone.utc)
            .replace(hour=10, minute=5, second=0, microsecond=0)
        )
        range_start = base_time - timedelta(days=1) + timedelta(minutes=2)
        range_end = base_time + timedelta(minutes=2)
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
            start_date=range_start.strftime("%Y-%m-%d %H:%M:%S"),
            end_date=range_end.strftime("%Y-%m-%d %H:%M:%S"),
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
            non_null_points[-1].strftime("%Y-%m-%d %H:%M"),
            base_time.replace(minute=0).strftime("%Y-%m-%d %H:%M"),
        )
        self.assertEqual(data["summary"], {"uptime": 100.0})

    def test_wifi_clients_chart_uses_uniform_10_minute_buckets_for_1d(self):
        metric = self._create_object_metric(
            name="wifi associations",
            key="hostapd",
            field_name="mac",
            extra_tags={"ifname": "wlan0"},
        )
        range_start = (
            (now() - timedelta(days=1))
            .astimezone(timezone.utc)
            .replace(hour=10, minute=7, second=0, microsecond=0)
        )
        for minutes, mac in (
            (1, "00:14:5c:00:00:01"),
            (11, "00:14:5c:00:00:02"),
            (21, "00:14:5c:00:00:03"),
        ):
            metric.write(mac, time=range_start + timedelta(minutes=minutes))
        chart = Chart(metric=metric, configuration="wifi_clients")
        chart.full_clean()
        chart.save()
        data = self._read_chart(
            chart,
            time="1d",
            start_date=range_start.strftime("%Y-%m-%d %H:%M:%S"),
            end_date=(range_start + timedelta(minutes=30)).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            timezone="UTC",
        )
        non_null_points = [
            datetime.strptime(timestamp, "%Y-%m-%d %H:%M")
            for timestamp, value in zip(data["x"], data["traces"][0][1])
            if value is not None
        ]
        self.assertGreaterEqual(len(non_null_points), 1)
        self.assertTrue(all(point.minute % 10 == 0 for point in non_null_points), data)
        self.assertEqual(data["summary"], {"wifi_clients": 3})

    def test_access_tech_chart_keeps_sparse_range_buckets(self):
        metric = self._create_object_metric(
            name="access technology",
            key="signal",
            field_name="access_tech",
            configuration="access_tech",
            extra_tags={"ifname": "wwan0"},
        )
        range_start = (
            (now() - timedelta(days=1))
            .astimezone(timezone.utc)
            .replace(hour=10, minute=7, second=0, microsecond=0)
        )
        metric.write(4, time=range_start + timedelta(minutes=1))
        metric.write(4, time=range_start + timedelta(minutes=11))
        chart = Chart(metric=metric, configuration="access_tech")
        chart.full_clean()
        chart.save()
        data = self._read_chart(
            chart,
            time="1d",
            start_date=range_start.strftime("%Y-%m-%d %H:%M:%S"),
            end_date=(range_start + timedelta(minutes=60)).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            timezone="UTC",
        )
        non_null_values = [value for value in data["traces"][0][1] if value is not None]
        self.assertEqual(non_null_values, [4, 4])
        self.assertGreaterEqual(len(data["x"]), 6, data)

    def test_ping_uptime_chart_zoom_range_uses_request_timezone(self):
        metric = self._create_object_metric(name="ping", configuration="ping")
        request_day = (now() - timedelta(days=1)).astimezone(timezone.utc).date()
        metric.write(
            1,
            extra_values={"loss": 0, "rtt_min": 1.0, "rtt_avg": 2.0, "rtt_max": 3.0},
            time=datetime(
                request_day.year,
                request_day.month,
                request_day.day,
                4,
                40,
                tzinfo=timezone.utc,
            ),
        )
        chart = Chart(metric=metric, configuration="uptime")
        chart.full_clean()
        chart.save()
        data = self._read_chart(
            chart,
            time="1d",
            start_date=f"{request_day:%Y-%m-%d} 10:00:00",
            end_date=f"{request_day:%Y-%m-%d} 11:00:00",
            timezone="Asia/Kolkata",
        )
        self.assertIn("x", data)
        self.assertTrue(data["traces"], data)
        self.assertEqual(data["traces"][0][0], "uptime")
        self.assertIn(100.0, data["traces"][0][1])
        self.assertEqual(data["summary"], {"uptime": 100.0})

    def test_ping_uptime_chart_daily_window_uses_request_timezone(self):
        metric = self._create_object_metric(name="ping", configuration="ping")
        india_timezone = timezone(timedelta(hours=5, minutes=30))
        write_day = (now() - timedelta(days=2)).astimezone(timezone.utc).date()
        write_time = datetime(
            write_day.year,
            write_day.month,
            write_day.day,
            20,
            0,
            tzinfo=timezone.utc,
        )
        local_midnight = write_time.astimezone(india_timezone).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        window_start = local_midnight - timedelta(days=1)
        window_end = local_midnight + timedelta(
            days=1,
            hours=23,
            minutes=59,
            seconds=59,
        )
        metric.write(
            1,
            extra_values={"loss": 0, "rtt_min": 1.0, "rtt_avg": 2.0, "rtt_max": 3.0},
            time=write_time,
        )
        chart = Chart(metric=metric, configuration="uptime")
        chart.full_clean()
        chart.save()
        data = self._read_chart(
            chart,
            time="30d",
            start_date=window_start.strftime("%Y-%m-%d %H:%M:%S"),
            end_date=window_end.strftime("%Y-%m-%d %H:%M:%S"),
            timezone="Asia/Kolkata",
        )
        non_null_points = [
            timestamp
            for timestamp, value in zip(data["x"], data["traces"][0][1])
            if value is not None
        ]
        self.assertEqual(non_null_points, [local_midnight.strftime("%Y-%m-%d %H:%M")])

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
            self._read_metric(short_metric, retention_policy=SHORT_RP)[0]["value"],
            75,
        )
        timeseries_db.delete_series(key=object_metric.key, tags=object_metric.tags)
        self.assertEqual(self._read_metric(object_metric), [])
        self.assertEqual(self._read_metric(general_metric)[0]["value"], 100)
        self.assertEqual(
            self._read_metric(short_metric, retention_policy=SHORT_RP)[0]["value"],
            75,
        )
        timeseries_db.delete_metric_data(key=general_metric.key)
        self.assertEqual(self._read_metric(general_metric), [])
        timeseries_db.delete_metric_data(key=short_metric.key)
        self.assertEqual(self._read_metric(short_metric, retention_policy=SHORT_RP), [])

    def test_delete_metric_data_without_filters_clears_default_and_short_streams(self):
        general_metric = self._create_general_metric(name="delete-all-general")
        short_metric = self._create_general_metric(name="delete-all-short")
        self._write_metric(general_metric, 100, check=False)
        self._write_metric(short_metric, 75, check=False, retention_policy=SHORT_RP)
        self.assertEqual(self._read_metric(general_metric)[0]["value"], 100)
        self.assertEqual(
            self._read_metric(short_metric, retention_policy=SHORT_RP)[0]["value"],
            75,
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
        self.assertEqual(policies[0]["duration"], "94608000s")
        self.assertEqual(policies[0]["replication"], 1)
        self.assertEqual(policies[1]["name"], SHORT_RP)
        self.assertEqual(policies[1]["default"], False)
        self.assertEqual(policies[1]["duration"], "86400s")
        self.assertEqual(policies[1]["replication"], 1)

    @capture_stderr()
    def test_write_failure_raises_timeseries_exception(self):
        mock_db = MagicMock()
        mock_db.index.side_effect = RuntimeError("write failed")
        with patch.dict(timeseries_db.__dict__, {"db": mock_db}), self.assertRaises(
            TimeseriesWriteException
        ):
            timeseries_db.write("test_write", {"value": 1})


@tag("timeseries_client", "elasticsearch")
class TestElasticsearchCheckIntegration(
    ElasticsearchIntegrationMixin,
    RequireTimeseriesBackendMixin,
    AutoWifiClientCheck,
    AutoDataCollectedCheck,
    TestDeviceMonitoringMixin,
    TransactionTestCase,
):
    _WIFI_CLIENTS = next(
        path
        for path, _name, _setting in check_settings.CHECK_CLASSES
        if path.endswith(".WifiClients")
    )
    _DATA_COLLECTED = next(
        path
        for path, _name, _setting in check_settings.CHECK_CLASSES
        if path.endswith(".DataCollected")
    )
    expected_backend = "elasticsearch"

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
            key="wifi_clients",
            object_id=device.pk,
        ).first()
        self.assertIsNotNone(
            raw_metric,
            list(
                Metric.objects.filter(object_id=device.pk).values_list(
                    "key",
                    flat=True,
                )
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


@tag("timeseries_client", "elasticsearch")
class TestElasticsearchDeviceApiIntegration(
    ElasticsearchIntegrationMixin,
    RequireTimeseriesBackendMixin,
    TestDeviceMonitoringMixin,
    TestCase,
):
    expected_backend = "elasticsearch"

    @classmethod
    def _get_class_patchers(cls):
        return super()._get_class_patchers() + (
            patch.object(
                device_tasks.write_device_metrics,
                "delay",
                side_effect=device_tasks.write_device_metrics.run,
            ),
        )

    def test_device_metric_post_and_get_round_trip(self):
        device_data = self.create_test_data()
        device = self.device_model.objects.get(pk=device_data.pk)
        response = self.client.get(
            f"{self._url(device.pk, device.key)}&time=1d&status=1&timezone=Asia/Kolkata"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("data", response.data)
        self.assertEqual(response.data["data"], device_data.data)
        self.assertIn("charts", response.data)
        self.assertGreater(len(response.data["charts"]), 0)
        for chart in response.data["charts"]:
            self.assertIn("traces", chart)
            self.assertIn("summary", chart)
            self.assertIn("summary_labels", chart)
            self.assertIn("colors", chart)

    def test_device_metric_csv_export_round_trip(self):
        device_data = self.create_test_data(no_resources=True)
        device = self.device_model.objects.get(pk=device_data.pk)
        response = self.client.get(f"{self._url(device.pk, device.key)}&csv=1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get("Content-Disposition"), "attachment; filename=data.csv"
        )
        self.assertEqual(response.get("Content-Type"), "text/csv")
        rows = response.content.decode("utf8").strip().split("\n")
        header = rows[0].strip().split(",")
        self.assertEqual(header[0], "time")
        self.assertIn("wifi_clients - WiFi clients: wlan0", header)
        self.assertIn("download - Traffic: wlan0", header)
        self.assertTrue(any(row.strip() for row in rows[1:]))

    def test_dashboard_timeseries_endpoint_round_trip(self):
        path = reverse("monitoring_general:api_dashboard_timeseries")
        org = self._create_org(name="org1", slug="org1")
        metric = self._create_general_metric(
            name="wifi_clients",
            configuration="general_clients",
            field_name="clients",
            main_tags={"ifname": "wlan0"},
            extra_tags={"organization_id": str(org.id)},
        )
        metric.write("00:23:4a:00:00:00")
        self.client.force_login(self._create_admin())
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertIn("x", response.data)
        self.assertIn("charts", response.data)
        chart = response.data["charts"][0]
        self.assertEqual(chart["traces"][0][0], "wifi_clients")
        self.assertEqual(chart["traces"][0][1][-1], 1)
        self.assertEqual(chart["summary"]["wifi_clients"], 1)
