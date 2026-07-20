from importlib import import_module
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from openwisp_monitoring.db.backends import load_backend, load_backend_module
from openwisp_monitoring.db.backends.base import (
    BackendQueryBundle,
    BaseTimeseriesClient,
)
from openwisp_monitoring.db.backends.influxdb2.client import (
    DatabaseClient,
    QueryResultSet,
)
from openwisp_monitoring.monitoring import configuration


class DummyTimeseriesClient(BaseTimeseriesClient):
    backend_name = "dummy"
    required_settings = ("BACKEND", "NAME")

    @property
    def use_udp(self):
        return False

    def create_database(self):
        return None

    def drop_database(self):
        return None

    def create_or_alter_retention_policy(self, name, duration):
        return None

    def query(self, query, precision=None, **kwargs):
        return None

    def write(self, name, values, **kwargs):
        return None

    def batch_write(self, metric_data):
        return None

    def read(self, key, fields, tags, **kwargs):
        return []

    def get_list_query(self, query, precision="s"):
        return []

    def get_list_retention_policies(self):
        return []

    def get_device_data_query(self, retention_policy, measurement, pk):
        return f"{retention_policy}:{measurement}:{pk}"

    def delete_metric_data(self, key=None, tags=None):
        return None

    def delete_series(self, key=None, tags=None):
        return None

    def validate_query(self, query):
        return False

    def get_query(
        self,
        chart_type,
        params,
        time,
        group_map,
        summary=False,
        fields=None,
        query=None,
        timezone=None,
    ):
        return query or ""

    def _get_top_fields(
        self,
        query,
        params,
        chart_type,
        group_map,
        number,
        time,
        timezone=None,
    ):
        return []


def _get_chart_keys_from_configuration():
    chart_query_keys = {
        id(query): key for key, query in configuration.chart_query.items()
    }
    required_keys = set()
    for metric in configuration.DEFAULT_METRICS.values():
        for chart_config in metric.get("charts", {}).values():
            query_key = chart_query_keys.get(id(chart_config.get("query")))
            if query_key:
                required_keys.add(query_key)
    return required_keys


class TestBackendContract(SimpleTestCase):
    backend_configs = {
        "openwisp_monitoring.db.backends.influxdb": {
            "BACKEND": "openwisp_monitoring.db.backends.influxdb",
            "USER": "openwisp",
            "PASSWORD": "openwisp",
            "NAME": "openwisp2",
            "HOST": "localhost",
            "PORT": "8086",
        },
        "openwisp_monitoring.db.backends.influxdb2": {
            "BACKEND": "openwisp_monitoring.db.backends.influxdb2",
            "PASSWORD": "token",
            "NAME": "openwisp2",
            "USER": "openwisp",
            "HOST": "localhost",
            "PORT": "8086",
        },
    }

    def test_backends_implement_contract(self):
        required_chart_keys = _get_chart_keys_from_configuration()
        for backend_path, config in self.backend_configs.items():
            with self.subTest(backend=backend_path):
                backend_module = import_module(backend_path)
                self.assertTrue(
                    issubclass(backend_module.DatabaseClient, BaseTimeseriesClient)
                )
                self.assertIsInstance(backend_module.queries, BackendQueryBundle)
                self.assertEqual(
                    backend_module.DatabaseClient.validate_settings(config),
                    config,
                )
                backend_module.queries.validate(
                    backend_module.DatabaseClient.backend_name
                )
                self.assertIsInstance(backend_module.queries.device_data_query, str)
                self.assertTrue(
                    callable(backend_module.DatabaseClient().get_device_data_query)
                )
                self.assertTrue(
                    required_chart_keys.issubset(
                        set(backend_module.queries.chart_query.keys())
                    )
                )

    def test_backends_reset_their_cached_state(self):
        backend_cached_attrs = {
            "openwisp_monitoring.db.backends.influxdb": ("db", "dbs", "use_udp"),
            "openwisp_monitoring.db.backends.influxdb2": (
                "db",
                "_write_api",
                "_query_api",
                "_delete_api",
                "use_udp",
            ),
        }
        for backend_path, attrs in backend_cached_attrs.items():
            with self.subTest(backend=backend_path):
                backend_module = import_module(backend_path)
                client = backend_module.DatabaseClient(db_name="initial-db")
                for attr in attrs:
                    client.__dict__[attr] = object()
                client.reset(db_name="reset-db")
                self.assertEqual(client.db_name, "reset-db")
                for attr in attrs:
                    self.assertNotIn(attr, client.__dict__)


class TestBackendLoader(SimpleTestCase):
    def _build_valid_backend(self):
        return SimpleNamespace(
            DatabaseClient=DummyTimeseriesClient,
            queries=BackendQueryBundle(
                chart_query={"cpu": {"dummy": "SELECT * FROM cpu"}},
                default_chart_query=["SELECT value FROM cpu", " WHERE object_id = 1"],
                device_data_query="SELECT data FROM {measurement}",
            ),
        )

    def test_load_backend_rejects_missing_backend_name(self):
        with patch("openwisp_monitoring.db.backends.import_module") as mocked_import:
            with self.assertRaisesMessage(
                ImproperlyConfigured,
                '"BACKEND" field is not declared in TIMESERIES_DATABASE',
            ):
                load_backend(config={"NAME": "openwisp2"})
        mocked_import.assert_not_called()

    @patch.dict(
        "openwisp_monitoring.db.backends.TIMESERIES_DB",
        {"NAME": "openwisp2"},
        clear=True,
    )
    def test_load_backend_module_rejects_missing_default_backend_name(self):
        with patch("openwisp_monitoring.db.backends.import_module") as mocked_import:
            with self.assertRaisesMessage(
                ImproperlyConfigured,
                '"BACKEND" field is not declared in TIMESERIES_DATABASE',
            ):
                load_backend_module()
        mocked_import.assert_not_called()

    def test_load_backend_rejects_invalid_backend_class(self):
        backend_module = self._build_valid_backend()
        backend_module.DatabaseClient = object
        with patch(
            "openwisp_monitoring.db.backends.import_module",
            return_value=backend_module,
        ):
            with self.assertRaisesMessage(
                ImproperlyConfigured,
                "must define a DatabaseClient subclassing BaseTimeseriesClient",
            ):
                load_backend(
                    backend_name="tests.dummy_backend",
                    config={"BACKEND": "tests.dummy_backend", "NAME": "openwisp2"},
                )

    def test_load_backend_rejects_missing_settings(self):
        backend_module = self._build_valid_backend()
        with patch(
            "openwisp_monitoring.db.backends.import_module",
            return_value=backend_module,
        ):
            with self.assertRaisesMessage(
                ImproperlyConfigured,
                '"NAME" field is not declared in TIMESERIES_DATABASE',
            ):
                load_backend(
                    backend_name="tests.dummy_backend",
                    config={"BACKEND": "tests.dummy_backend"},
                )

    def test_load_backend_rejects_missing_query_bundle(self):
        backend_module = self._build_valid_backend()
        backend_module.queries = object()
        with patch(
            "openwisp_monitoring.db.backends.import_module",
            return_value=backend_module,
        ):
            with self.assertRaisesMessage(
                ImproperlyConfigured,
                "must expose a BackendQueryBundle instance as 'queries'",
            ):
                load_backend(
                    backend_name="tests.dummy_backend",
                    config={"BACKEND": "tests.dummy_backend", "NAME": "openwisp2"},
                )

    def test_load_backend_rejects_invalid_query_bundle(self):
        backend_module = self._build_valid_backend()
        backend_module.queries = BackendQueryBundle(
            chart_query={"cpu": {"other": "SELECT * FROM cpu"}},
            default_chart_query=["SELECT value FROM cpu"],
            device_data_query="SELECT data FROM {measurement}",
        )
        with patch(
            "openwisp_monitoring.db.backends.import_module",
            return_value=backend_module,
        ):
            with self.assertRaisesMessage(
                ImproperlyConfigured,
                "Backend query bundle is missing the 'dummy' key",
            ):
                load_backend(
                    backend_name="tests.dummy_backend",
                    config={"BACKEND": "tests.dummy_backend", "NAME": "openwisp2"},
                )

    def test_load_backend_rejects_empty_default_chart_query(self):
        backend_module = self._build_valid_backend()
        backend_module.queries = BackendQueryBundle(
            chart_query={"cpu": {"dummy": "SELECT * FROM cpu"}},
            default_chart_query=[],
            device_data_query="SELECT data FROM {measurement}",
        )
        with patch(
            "openwisp_monitoring.db.backends.import_module",
            return_value=backend_module,
        ):
            with self.assertRaisesMessage(
                ImproperlyConfigured,
                "Backend query bundle must define a non-empty default_chart_query.",
            ):
                load_backend(
                    backend_name="tests.dummy_backend",
                    config={"BACKEND": "tests.dummy_backend", "NAME": "openwisp2"},
                )

    def test_load_backend_rejects_empty_device_data_query(self):
        backend_module = self._build_valid_backend()
        backend_module.queries = BackendQueryBundle(
            chart_query={"cpu": {"dummy": "SELECT * FROM cpu"}},
            default_chart_query=["SELECT value FROM cpu"],
            device_data_query="",
        )
        with patch(
            "openwisp_monitoring.db.backends.import_module",
            return_value=backend_module,
        ):
            with self.assertRaisesMessage(
                ImproperlyConfigured,
                "Backend query bundle must define a non-empty device_data_query.",
            ):
                load_backend(
                    backend_name="tests.dummy_backend",
                    config={"BACKEND": "tests.dummy_backend", "NAME": "openwisp2"},
                )

    def test_load_backend_returns_validated_backend_module(self):
        backend_module = self._build_valid_backend()
        with patch(
            "openwisp_monitoring.db.backends.import_module",
            return_value=backend_module,
        ):
            loaded = load_backend(
                backend_name="tests.dummy_backend",
                config={"BACKEND": "tests.dummy_backend", "NAME": "openwisp2"},
            )
        self.assertIs(loaded, backend_module)

    def test_load_backend_preserves_module_attribute_error(self):
        with patch(
            "openwisp_monitoring.db.backends.import_module",
            side_effect=AttributeError("module attribute failed", name="broken_attr"),
        ):
            with self.assertRaisesMessage(AttributeError, "module attribute failed"):
                load_backend(
                    backend_name="tests.dummy_backend",
                    config={"BACKEND": "tests.dummy_backend", "NAME": "openwisp2"},
                )

    def test_load_backend_preserves_dependency_import_error(self):
        errors = (
            ImportError("cannot import name 'missing_dependency'"),
            ModuleNotFoundError(
                "No module named 'missing_dependency'",
                name="missing_dependency",
            ),
        )
        for error in errors:
            with self.subTest(error=error.__class__.__name__):
                with patch(
                    "openwisp_monitoring.db.backends.import_module",
                    side_effect=error,
                ):
                    with self.assertRaisesMessage(error.__class__, str(error)):
                        load_backend(
                            backend_name="tests.dummy_backend",
                            config={
                                "BACKEND": "tests.dummy_backend",
                                "NAME": "openwisp2",
                            },
                        )

    def test_get_default_chart_query_rejects_empty_sequence_descriptor(self):
        client = DummyTimeseriesClient().attach_queries(
            BackendQueryBundle(
                chart_query={"cpu": {"dummy": "SELECT * FROM cpu"}},
                default_chart_query=[],
                device_data_query="SELECT data FROM {measurement}",
            )
        )
        with self.assertRaisesMessage(
            ImproperlyConfigured,
            "Backend query bundle must define a non-empty default_chart_query.",
        ):
            client.get_default_chart_query()


class TestInfluxDb2ClientUrl(SimpleTestCase):
    base_config = {
        "BACKEND": "openwisp_monitoring.db.backends.influxdb2",
        "PASSWORD": "token",
        "NAME": "openwisp2",
        "USER": "openwisp",
        "HOST": "localhost",
        "PORT": "8086",
    }

    @patch.dict(
        "openwisp_monitoring.db.backends.influxdb2.client.TIMESERIES_DB",
        base_config,
        clear=True,
    )
    @patch("openwisp_monitoring.db.backends.influxdb2.client.logger.warning")
    @patch("openwisp_monitoring.db.backends.influxdb2.client.InfluxDBClient")
    def test_db_warns_for_http_fallback_url(self, mock_client, mocked_warning):
        client = DatabaseClient()
        client.db
        mock_client.assert_called_once_with(
            url="http://localhost:8086", token="token", org="openwisp"
        )
        mocked_warning.assert_called_once()

    @patch.dict(
        "openwisp_monitoring.db.backends.influxdb2.client.TIMESERIES_DB",
        {**base_config, "URL": "https://influxdb.example.com:8086"},
        clear=True,
    )
    @patch("openwisp_monitoring.db.backends.influxdb2.client.logger.warning")
    @patch("openwisp_monitoring.db.backends.influxdb2.client.InfluxDBClient")
    def test_db_does_not_warn_for_https_url(self, mock_client, mocked_warning):
        client = DatabaseClient()
        client.db
        mock_client.assert_called_once_with(
            url="https://influxdb.example.com:8086",
            token="token",
            org="openwisp",
        )
        mocked_warning.assert_not_called()

    def test_validate_settings_accepts_url_without_host_and_port(self):
        config = {
            "BACKEND": "openwisp_monitoring.db.backends.influxdb2",
            "PASSWORD": "token",
            "NAME": "openwisp2",
            "USER": "openwisp",
            "URL": "http://influxdb.example.com:8086",
        }
        self.assertEqual(DatabaseClient.validate_settings(config), config)

    def test_validate_settings_accepts_udp_options(self):
        config = {
            **self.base_config,
            "OPTIONS": {
                "udp_writes": True,
                "udp_host": "telegraf",
                "udp_port": 8089,
            },
        }
        self.assertEqual(DatabaseClient.validate_settings(config), config)

    def test_validate_settings_rejects_missing_url_and_host_port(self):
        config = {
            "BACKEND": "openwisp_monitoring.db.backends.influxdb2",
            "PASSWORD": "token",
            "NAME": "openwisp2",
            "USER": "openwisp",
        }
        with self.assertRaisesMessage(
            ImproperlyConfigured,
            'InfluxDB2 TIMESERIES_DATABASE must define either "URL" or both "HOST" and "PORT".',
        ):
            DatabaseClient.validate_settings(config)

    def test_close_shuts_down_cached_client_and_clears_cached_state(self):
        client = DatabaseClient()
        mock_db = MagicMock()
        client.__dict__["db"] = mock_db
        client.__dict__["_write_api"] = object()
        client.__dict__["_query_api"] = object()
        client.__dict__["_delete_api"] = object()
        client.__dict__["use_udp"] = object()
        client.__dict__["_udp_host"] = object()
        client.__dict__["_udp_port"] = object()
        client.close()
        mock_db.close.assert_called_once_with()
        self.assertNotIn("db", client.__dict__)
        self.assertNotIn("_write_api", client.__dict__)
        self.assertNotIn("_query_api", client.__dict__)
        self.assertNotIn("_delete_api", client.__dict__)
        self.assertNotIn("use_udp", client.__dict__)
        self.assertNotIn("_udp_host", client.__dict__)
        self.assertNotIn("_udp_port", client.__dict__)

    def _mock_buckets_api(self, client):
        mock_db = MagicMock()
        mock_api = MagicMock()
        mock_db.buckets_api.return_value = mock_api
        client.__dict__["db"] = mock_db
        return mock_api

    def test_create_database_ignores_missing_bucket_lookup_error(self):
        client = DatabaseClient()
        mock_api = self._mock_buckets_api(client)
        mock_api.find_bucket_by_name.side_effect = client.client_error(
            message="could not find bucket"
        )
        client.create_database()
        mock_api.create_bucket.assert_called_once_with(
            bucket_name=client.db_name,
            org=client.user,
        )

    @patch("openwisp_monitoring.utils.sleep")
    def test_create_database_reraises_lookup_error(self, mocked_sleep):
        client = DatabaseClient()
        mock_api = self._mock_buckets_api(client)
        mock_api.find_bucket_by_name.side_effect = client.client_error(
            message="lookup failed"
        )
        with self.assertRaises(client.client_error):
            client.create_database()
        mock_api.create_bucket.assert_not_called()
        mocked_sleep.assert_called()

    @patch("openwisp_monitoring.db.backends.influxdb2.client.logger.debug")
    def test_drop_database_ignores_missing_bucket_lookup_error(self, mocked_debug):
        client = DatabaseClient()
        mock_api = self._mock_buckets_api(client)
        mock_api.find_bucket_by_name.side_effect = client.client_error(
            message="could not find bucket"
        )
        client.drop_database()
        mock_api.delete_bucket.assert_not_called()
        self.assertEqual(
            mocked_debug.call_args_list,
            [
                call(f'InfluxDB2 bucket "{client.db_name}" not found'),
                call(f'InfluxDB2 bucket "{client.db_name}_short" not found'),
            ],
        )

    @patch("openwisp_monitoring.utils.sleep")
    def test_drop_database_reraises_lookup_error(self, mocked_sleep):
        client = DatabaseClient()
        mock_api = self._mock_buckets_api(client)
        mock_api.find_bucket_by_name.side_effect = client.client_error(
            message="lookup failed"
        )
        with self.assertRaises(client.client_error):
            client.drop_database()
        mock_api.delete_bucket.assert_not_called()
        mocked_sleep.assert_called()

    def test_get_list_retention_policies_ignores_missing_bucket_lookup_error(self):
        client = DatabaseClient()
        mock_api = self._mock_buckets_api(client)
        short_bucket = MagicMock()
        short_rule = MagicMock()
        short_rule.every_seconds = 86400
        short_bucket.retention_rules = [short_rule]
        mock_api.find_bucket_by_name.side_effect = [
            client.client_error(message="could not find bucket"),
            short_bucket,
        ]
        policies = client.get_list_retention_policies()
        self.assertEqual(
            policies,
            [
                {
                    "name": "short",
                    "default": False,
                    "duration": "86400s",
                    "replication": 1,
                }
            ],
        )

    @patch("openwisp_monitoring.utils.sleep")
    def test_get_list_retention_policies_reraises_lookup_error(self, mocked_sleep):
        client = DatabaseClient()
        mock_api = self._mock_buckets_api(client)
        mock_api.find_bucket_by_name.side_effect = client.client_error(
            message="lookup failed"
        )
        with self.assertRaises(client.client_error):
            client.get_list_retention_policies()
        mocked_sleep.assert_called()

    def test_read_preserves_selected_field_with_cross_field_where(self):
        client = DatabaseClient()
        points = [
            {
                "_measurement": "cpu",
                "_field": "usage",
                "_value": 72,
                "time": 1,
                "host": "router1",
            },
            {
                "_measurement": "cpu",
                "_field": "status",
                "_value": "ok",
                "time": 1,
                "host": "router1",
            },
            {
                "_measurement": "cpu",
                "_field": "usage",
                "_value": 91,
                "time": 2,
                "host": "router1",
            },
            {
                "_measurement": "cpu",
                "_field": "status",
                "_value": "warn",
                "time": 2,
                "host": "router1",
            },
        ]

        def mock_query(flux_query, **kwargs):
            if 'r._field == "status" and r._value == "ok"' in flux_query:
                return QueryResultSet([points[1]])
            return QueryResultSet(points)

        with patch.object(client, "query", side_effect=mock_query):
            result = client.read(
                key="cpu",
                fields=["usage"],
                tags={},
                where=[("status", "=", "ok")],
            )
        self.assertEqual(result, [{"time": 1, "host": "router1", "usage": 72}])

    def test_normalize_read_points_keeps_measurements_separate(self):
        client = DatabaseClient()
        points = [
            {
                "_measurement": "cpu",
                "_field": "usage",
                "_value": 72,
                "time": 1,
                "host": "router1",
            },
            {
                "_measurement": "memory",
                "_field": "usage",
                "_value": 91,
                "time": 1,
                "host": "router1",
            },
        ]
        self.assertEqual(
            client._normalize_read_points(points),
            [
                {"time": 1, "host": "router1", "usage": 72},
                {"time": 1, "host": "router1", "usage": 91},
            ],
        )

    @patch.dict(
        "openwisp_monitoring.db.backends.influxdb2.client.TIMESERIES_DB",
        {
            **base_config,
            "OPTIONS": {
                "udp_writes": True,
                "udp_host": "telegraf",
                "udp_port": 8089,
            },
        },
        clear=True,
    )
    def test_use_udp_reads_udp_option(self):
        self.assertIs(DatabaseClient().use_udp, True)

    @patch.dict(
        "openwisp_monitoring.db.backends.influxdb2.client.TIMESERIES_DB",
        {
            **base_config,
            "OPTIONS": {
                "udp_writes": True,
                "udp_host": "telegraf",
                "udp_port": 8089,
            },
        },
        clear=True,
    )
    @patch("openwisp_monitoring.db.backends.influxdb2.client.socket.socket")
    def test_write_uses_udp_line_protocol(self, mocked_socket):
        client = DatabaseClient()
        client.write(
            "test_measurement",
            {"field1": 10},
            tags={"host": "router1"},
            timestamp="2024-03-25T12:30:45Z",
        )
        mocked_socket.return_value.__enter__.return_value.sendto.assert_called_once_with(
            b"test_measurement,host=router1 field1=10i 1711369845000000000",
            ("telegraf", 8089),
        )

    @patch.dict(
        "openwisp_monitoring.db.backends.influxdb2.client.TIMESERIES_DB",
        {
            **base_config,
            "OPTIONS": {
                "udp_writes": True,
                "udp_host": "telegraf",
                "udp_port": 8089,
            },
        },
        clear=True,
    )
    @patch("openwisp_monitoring.db.backends.influxdb2.client.socket.socket")
    def test_batch_write_maps_retention_policy_to_udp_port(self, mocked_socket):
        client = DatabaseClient()
        client.batch_write(
            [
                {
                    "name": "default_measurement",
                    "values": {"field1": 10},
                    "timestamp": "2024-03-25T12:30:45Z",
                },
                {
                    "name": "short_measurement",
                    "values": {"field1": 20},
                    "retention_policy": "short",
                    "timestamp": "2024-03-25T12:31:45Z",
                },
            ]
        )
        sendto = mocked_socket.return_value.__enter__.return_value.sendto
        self.assertEqual(
            sendto.call_args_list,
            [
                call(
                    b"default_measurement field1=10i 1711369845000000000",
                    ("telegraf", 8089),
                ),
                call(
                    b"short_measurement field1=20i 1711369905000000000",
                    ("telegraf", 8090),
                ),
            ],
        )

    @patch.dict(
        "openwisp_monitoring.db.backends.influxdb2.client.TIMESERIES_DB",
        {
            **base_config,
            "OPTIONS": {
                "udp_writes": True,
                "udp_host": "telegraf",
                "udp_port": 8089,
            },
        },
        clear=True,
    )
    def test_autogen_retention_policy_uses_default_udp_port(self):
        self.assertEqual(DatabaseClient()._get_udp_port("autogen"), 8089)

    @patch.dict(
        "openwisp_monitoring.db.backends.influxdb2.client.TIMESERIES_DB",
        {
            **base_config,
            "OPTIONS": {
                "udp_writes": True,
                "udp_host": "telegraf",
                "udp_port": 8089,
            },
        },
        clear=True,
    )
    def test_udp_write_falls_back_to_http_for_large_packets(self):
        client = DatabaseClient()
        with patch.object(client, "_write_api") as mock_write_api:
            client.write("test_measurement", {"field1": "é" * 40000})
        mock_write_api.write.assert_called_once()

    def test_reset_shuts_down_cached_client_and_clears_cached_state(self):
        client = DatabaseClient(db_name="initial-db")
        mock_db = MagicMock()
        client.__dict__["db"] = mock_db
        client.__dict__["_write_api"] = object()
        client.__dict__["_query_api"] = object()
        client.__dict__["_delete_api"] = object()
        client.__dict__["use_udp"] = object()
        client.__dict__["_udp_host"] = object()
        client.__dict__["_udp_port"] = object()
        client.reset(db_name="reset-db")
        mock_db.close.assert_called_once_with()
        self.assertEqual(client.db_name, "reset-db")
        self.assertNotIn("db", client.__dict__)
        self.assertNotIn("_write_api", client.__dict__)
        self.assertNotIn("_query_api", client.__dict__)
        self.assertNotIn("_delete_api", client.__dict__)
        self.assertNotIn("use_udp", client.__dict__)
        self.assertNotIn("_udp_host", client.__dict__)
        self.assertNotIn("_udp_port", client.__dict__)
