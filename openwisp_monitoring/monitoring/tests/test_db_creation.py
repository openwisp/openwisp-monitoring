import io
from contextlib import redirect_stdout
from unittest import skipIf
from unittest.mock import patch

from django.apps import apps
from django.test import TestCase
from requests.exceptions import ConnectionError
from swapper import is_swapped

from ..utils import get_db


def mock_create_database(self, db):
    raise ConnectionError


@skipIf(is_swapped('monitoring', 'Metric'), 'Running tests on sample_app')
class TestDatabase(TestCase):
    @patch('openwisp_monitoring.monitoring.settings.INFLUXDB_DATABASE', 'test_db')
    @patch('openwisp_monitoring.monitoring.apps.MonitoringConfig.warn_and_delay')
    @patch('influxdb.client.InfluxDBClient.create_database', mock_create_database)
    def test_check_retry(self, mock):
        try:
            apps.get_app_config('monitoring').create_database()
        except ConnectionError:
            pass
        get_db().drop_database('test_db')
        self.assertEqual(mock.call_count, 5)

    @patch('openwisp_monitoring.monitoring.apps.sleep', return_value=None)
    def test_warn_and_delay(self, mock):
        f = io.StringIO()
        with redirect_stdout(f):
            apps.get_app_config('monitoring').warn_and_delay(1)
        self.assertEqual(
            f.getvalue(),
            'Got error while connecting to timeseries DB. '
            'Retrying again in 3 seconds (attempt n. 1 out of 5).\n',
        )
        mock.assert_called_with(3)
