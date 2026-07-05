from importlib import import_module
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from openwisp_monitoring.db.backends import load_backend
from openwisp_monitoring.db.backends.base import (
    BackendQueryBundle,
    BaseTimeseriesClient,
)
from openwisp_monitoring.db.backends.influxdb2.client import DatabaseClient
from openwisp_monitoring.monitoring import configuration


class DummyDeviceDataQuery:
    def format(self, retention_policy, measurement, pk):
        return f"{retention_policy}:{measurement}:{pk}"


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
            "TOKEN": "token",
            "NAME": "openwisp2",
            "ORG": "openwisp",
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
                self.assertTrue(
                    callable(backend_module.queries.device_data_query.format)
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
                device_data_query=DummyDeviceDataQuery(),
            ),
        )

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
            device_data_query=DummyDeviceDataQuery(),
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

    def test_get_default_chart_query_rejects_empty_sequence_descriptor(self):
        client = DummyTimeseriesClient().attach_queries(
            BackendQueryBundle(
                chart_query={"cpu": {"dummy": "SELECT * FROM cpu"}},
                default_chart_query=[],
                device_data_query=DummyDeviceDataQuery(),
            )
        )
        with self.assertRaisesMessage(
            ImproperlyConfigured,
            "Backend query bundle must define a non-empty default_chart_query.",
        ):
            client.get_default_chart_query()


class TestInfluxDB2ClientURL(SimpleTestCase):
    base_config = {
        "BACKEND": "openwisp_monitoring.db.backends.influxdb2",
        "TOKEN": "token",
        "NAME": "openwisp2",
        "ORG": "openwisp",
        "HOST": "localhost",
        "PORT": "8086",
    }

    @patch.dict(
        "openwisp_monitoring.db.backends.influxdb2.client.TIMESERIES_DB",
        base_config,
        clear=True,
    )
    @patch("openwisp_monitoring.db.backends.influxdb2.client.InfluxDBClient")
    def test_db_uses_http_fallback_url(self, mock_client):
        client = DatabaseClient()
        client.db
        mock_client.assert_called_once_with(
            url="http://localhost:8086", token="token", org="openwisp"
        )

    @patch.dict(
        "openwisp_monitoring.db.backends.influxdb2.client.TIMESERIES_DB",
        {**base_config, "URL": "http://influxdb.example.com:8086"},
        clear=True,
    )
    @patch("openwisp_monitoring.db.backends.influxdb2.client.logger.warning")
    @patch("openwisp_monitoring.db.backends.influxdb2.client.InfluxDBClient")
    def test_db_warns_for_explicit_insecure_http_url(self, mock_client, mocked_warning):
        client = DatabaseClient()
        client.db
        mock_client.assert_called_once_with(
            url="http://influxdb.example.com:8086",
            token="token",
            org="openwisp",
        )
        mocked_warning.assert_called_once()
