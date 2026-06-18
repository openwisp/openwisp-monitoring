import os
from unittest import SkipTest
from unittest.mock import patch

from django.apps import apps
from django.test import TestCase, tag
from requests.exceptions import ConnectionError

from openwisp_monitoring.settings import MONITORING_TIMESERIES_RETRY_OPTIONS


class _TestDatabaseRetryMixin(TestCase):
    app = "monitoring"
    expected_backend = None
    patch_target = None

    @classmethod
    def setUpClass(cls):
        if os.environ.get("TIMESERIES_BACKEND") != cls.expected_backend:
            raise SkipTest(
                f'Set TIMESERIES_BACKEND="{cls.expected_backend}" to run these tests.'
            )
        super().setUpClass()

    def _assert_check_retry(self):
        max_retries = MONITORING_TIMESERIES_RETRY_OPTIONS.get("max_retries")
        delay = MONITORING_TIMESERIES_RETRY_OPTIONS.get("delay")
        with patch(self.patch_target, side_effect=ConnectionError()) as mock:
            with patch("openwisp_monitoring.utils.sleep") as sleep_mock:
                with patch("logging.Logger.info") as mocked_logger:
                    with self.assertRaises(ConnectionError):
                        apps.get_app_config(self.app).ready()
                    self.assertEqual(mocked_logger.call_count, max_retries)
                    mocked_logger.assert_called_with(
                        'Error while executing method "create_database":'
                        f"\n\nAttempt {max_retries} out of {max_retries}.\n"
                    )
                self.assertEqual(mock.call_count, max_retries)
                self.assertEqual(sleep_mock.call_count, max_retries - 3)
                sleep_mock.assert_called_with(delay)


@tag("tsdb_influxdb")
class TestDatabaseInfluxDB(_TestDatabaseRetryMixin):
    expected_backend = "influxdb"
    patch_target = "influxdb.InfluxDBClient.create_database"

    def test_check_retry(self):
        self._assert_check_retry()


@tag("tsdb_influxdb2")
class TestDatabaseInfluxDB2(_TestDatabaseRetryMixin):
    expected_backend = "influxdb2"
    patch_target = (
        "openwisp_monitoring.db.backends.influxdb2.client.InfluxDBClient.buckets_api"
    )

    def test_check_retry(self):
        self._assert_check_retry()
