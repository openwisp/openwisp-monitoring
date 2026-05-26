from time import sleep

from django.conf import settings
from django.core.cache import cache
from django.test import TestCase, tag
from django.utils.timezone import now
from swapper import load_model

from openwisp_monitoring.db import timeseries_db
from openwisp_monitoring.db.backends import TIMESERIES_DB
from openwisp_monitoring.monitoring.configuration import (
    register_metric,
    unregister_metric,
)
from openwisp_monitoring.monitoring.tests import test_notification

Metric = load_model("monitoring", "Metric")


@tag("timeseries_client")
class TestTimeseriesBackendContract(TestCase):
    original_db_name = TIMESERIES_DB["NAME"]
    test_db_name = f"{original_db_name}_contract_test"
    metric_configuration = "contract_metric"
    metric_config = {
        "name": "Contract Metric",
        "key": "{key}",
        "field_name": "{field_name}",
        "label": "Contract Metric",
        "notification": test_notification,
    }

    @classmethod
    def setUpClass(cls):
        cls._original_client_db_name = timeseries_db.db_name
        timeseries_db.db_name = cls.test_db_name
        cls._clear_timeseries_client_cache()
        timeseries_db.create_database()
        register_metric(cls.metric_configuration, cls.metric_config)
        cache.clear()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        try:
            timeseries_db.drop_database()
            unregister_metric(cls.metric_configuration)
            cache.clear()
            timeseries_db.db_name = cls._original_client_db_name
            cls._clear_timeseries_client_cache()
        finally:
            super().tearDownClass()

    @classmethod
    def _clear_timeseries_client_cache(cls):
        for attr in ("db", "dbs", "_write_api", "_query_api", "_delete_api", "use_udp"):
            timeseries_db.__dict__.pop(attr, None)

    def tearDown(self):
        timeseries_db.delete_metric_data()
        super().tearDown()

    def _timestamp(self):
        return now().isoformat()

    def _read_until(self, key, fields, tags=None, **kwargs):
        tags = tags or {}
        for _attempt in range(10):
            points = timeseries_db.read(key=key, fields=fields, tags=tags, **kwargs)
            if points:
                return points
            sleep(0.2)
        return points

    def _assert_field_value(self, point, field, value):
        self.assertIn(field, point)
        self.assertEqual(point[field], value)

    def test_active_backend_contract_metadata(self):
        backend_name = timeseries_db.backend_name
        self.assertIn(backend_name, ("influxdb", "influxdb2"))
        self.assertTrue(settings.TIMESERIES_DATABASE["BACKEND"].endswith(backend_name))

    def test_write_read_delete_single_metric(self):
        key = "contract_single_metric"
        timeseries_db.write(
            key,
            {"value": 42},
            tags={"scope": "single"},
            timestamp=self._timestamp(),
        )

        points = self._read_until(key, "value", tags={"scope": "single"})

        self.assertIsInstance(points, list)
        self.assertEqual(len(points), 1)
        self._assert_field_value(points[0], "value", 42)

        timeseries_db.delete_metric_data(key=key)
        self.assertEqual(timeseries_db.read(key=key, fields="value", tags={}), [])

    def test_write_read_with_tags(self):
        key = "contract_tagged_metric"
        timeseries_db.write(
            key,
            {"value": 10},
            tags={"host": "alpha"},
            timestamp=self._timestamp(),
        )
        timeseries_db.write(
            key,
            {"value": 20},
            tags={"host": "beta"},
            timestamp=self._timestamp(),
        )

        points = self._read_until(key, "value", tags={"host": "beta"})

        self.assertEqual(len(points), 1)
        self._assert_field_value(points[0], "value", 20)

    def test_batch_write_contract(self):
        key = "contract_batch_metric"
        timeseries_db.batch_write(
            [
                {
                    "name": key,
                    "values": {"value": 11},
                    "tags": {"role": "first"},
                    "timestamp": self._timestamp(),
                },
                {
                    "name": key,
                    "values": {"value": 22},
                    "tags": {"role": "second"},
                    "timestamp": self._timestamp(),
                },
            ]
        )

        first_points = self._read_until(key, "value", tags={"role": "first"})
        second_points = self._read_until(key, "value", tags={"role": "second"})

        self.assertEqual(len(first_points), 1)
        self.assertEqual(len(second_points), 1)
        self._assert_field_value(first_points[0], "value", 11)
        self._assert_field_value(second_points[0], "value", 22)

    def test_metric_model_write_read_contract(self):
        metric = Metric(
            name="Contract model metric",
            key="contract_model_metric",
            field_name="value",
            configuration=self.metric_configuration,
        )
        metric.full_clean()
        metric.save()

        metric.write(77, check=False)
        points = self._read_until(metric.key, metric.field_name, tags=metric.tags)

        self.assertEqual(len(points), 1)
        self._assert_field_value(points[0], metric.field_name, 77)
