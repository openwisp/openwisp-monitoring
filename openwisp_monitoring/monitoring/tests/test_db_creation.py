from unittest.mock import patch

from django.apps import apps
from django.test import TestCase
from influxdb import InfluxDBClient
from requests.exceptions import ConnectionError

from openwisp_monitoring.settings import MONITORING_TIMESERIES_RETRY_OPTIONS


class TestDatabase(TestCase):
    app = 'monitoring'

    @patch.object(InfluxDBClient, 'create_database', side_effect=ConnectionError())
    @patch('openwisp_monitoring.utils.sleep')
    def test_check_retry(self, sleep_mock, mock):
        max_retries = MONITORING_TIMESERIES_RETRY_OPTIONS.get('max_retries')
        delay = MONITORING_TIMESERIES_RETRY_OPTIONS.get('delay')
        with patch('logging.Logger.info') as mocked_logger:
            with self.assertRaises(ConnectionError):
                apps.get_app_config(self.app).ready()
            self.assertEqual(mocked_logger.call_count, max_retries)
            mocked_logger.assert_called_with(
                'Error while executing method "create_database":'
                f'\n\nAttempt {max_retries} out of {max_retries}.\n'
            )
        self.assertEqual(mock.call_count, max_retries)
        self.assertEqual(sleep_mock.call_count, max_retries - 3)
        sleep_mock.assert_called_with(delay)
