import io
from contextlib import redirect_stdout
from unittest.mock import patch

from django.apps import apps
from django.conf import settings
from django.test import TestCase
from requests.exceptions import ConnectionError

from ...db import TimeseriesDB

TIMESERIES_DB = getattr(settings, 'TIMESERIES_DATABASE')


def mock_create_database(**kwargs):
    raise ConnectionError


class TestDatabase(TestCase):
    app = 'monitoring'

    @patch.dict(TIMESERIES_DB, {'NAME': 'test_db'})
    @patch('openwisp_monitoring.monitoring.apps.MonitoringConfig.warn_and_delay')
    @patch('openwisp_monitoring.db.TimeseriesDB.create_database', mock_create_database)
    def test_check_retry(self, mock):
        try:
            apps.get_app_config(self.app).create_database()
        except ConnectionError:
            pass
        TimeseriesDB.drop_database('test_db')
        self.assertEqual(mock.call_count, 5)

    @patch('openwisp_monitoring.monitoring.apps.sleep', return_value=None)
    def test_warn_and_delay(self, mock):
        f = io.StringIO()
        with redirect_stdout(f):
            apps.get_app_config(self.app).warn_and_delay(1)
        self.assertEqual(
            f.getvalue(),
            'Got error while connecting to timeseries DB. '
            'Retrying again in 3 seconds (attempt n. 1 out of 5).\n',
        )
        mock.assert_called_with(3)
