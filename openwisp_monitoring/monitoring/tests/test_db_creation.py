import io
from contextlib import redirect_stdout
from unittest.mock import patch

from django.apps import apps
from django.test import TestCase
from requests.exceptions import ConnectionError


def mock_create_database(**kwargs):
    raise ConnectionError


class TestDatabase(TestCase):
    app = 'monitoring'

    @patch('openwisp_monitoring.monitoring.apps.MonitoringConfig.warn_and_delay')
    @patch('openwisp_monitoring.db.timeseries_db.create_database', mock_create_database)
    def test_check_retry(self, mock):
        try:
            apps.get_app_config(self.app).create_database()
        except ConnectionError:
            pass
        self.assertEqual(mock.call_count, 5)

    @patch('openwisp_monitoring.monitoring.apps.sleep', return_value=None)
    def test_warn_and_delay(self, mock):
        f = io.StringIO()
        with redirect_stdout(f):
            apps.get_app_config(self.app).warn_and_delay(1)
        self.assertEqual(
            f.getvalue(),
            'Got error while connecting to timeseries database. '
            'Retrying again in 3 seconds (attempt n. 1 out of 5).\n',
        )
        mock.assert_called_with(3)
