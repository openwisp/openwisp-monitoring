import os
from unittest import SkipTest
from unittest.mock import patch

from django.apps import apps
from django.test import TestCase, tag
from requests.exceptions import ConnectionError

from openwisp_monitoring.settings import MONITORING_TIMESERIES_RETRY_OPTIONS


class TestDatabaseRetryMixin(TestCase):
    app = "monitoring"
    expected_backend = None

    @classmethod
    def setUpClass(cls):
        if os.environ.get("TIMESERIES_BACKEND", "influxdb") != cls.expected_backend:
            raise SkipTest(
                f'Set TIMESERIES_BACKEND="{cls.expected_backend}" to run these tests.'
            )
        super().setUpClass()

    def _assert_check_retry(self, mock, sleep_mock):
        max_retries = MONITORING_TIMESERIES_RETRY_OPTIONS.get("max_retries")
        delay = MONITORING_TIMESERIES_RETRY_OPTIONS.get("delay")
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


@tag("influxdb1")
class TestDatabaseInfluxDB(TestDatabaseRetryMixin):
    expected_backend = "influxdb"

    @patch("openwisp_monitoring.utils.sleep")
    @patch("influxdb.InfluxDBClient.create_database", side_effect=ConnectionError())
    def test_check_retry(self, mock, sleep_mock):
        self._assert_check_retry(mock, sleep_mock)


@tag("influxdb2")
class TestDatabaseInfluxDB2(TestDatabaseRetryMixin):
    expected_backend = "influxdb2"

    @patch("openwisp_monitoring.utils.sleep")
    @patch(
        "openwisp_monitoring.db.backends.influxdb2.client.InfluxDBClient.buckets_api",
        side_effect=ConnectionError(),
    )
    def test_check_retry(self, mock, sleep_mock):
        self._assert_check_retry(mock, sleep_mock)
