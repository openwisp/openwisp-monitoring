from unittest.mock import patch

from django.test import TestCase
from freezegun import freeze_time

from .. import settings as app_settings
from .. import tasks


class TestRunWifiClientChecks(TestCase):
    _WIFI_CLIENT = app_settings.CHECK_CLASSES[3][0]

    @patch.object(tasks, 'run_checks')
    def test_wifi_client_check_snooze_schedule_empty(self, mocked_run_checks):
        tasks.run_wifi_client_checks()
        mocked_run_checks.assert_called_with(checks=[self._WIFI_CLIENT])

    @patch.object(
        tasks,
        'WIFI_CLIENT_CHECK_SNOOZE_SCHEDULE',
        [
            ('01-26', '01-26'),
            ('06-15', '08-31'),
            ('12-25', '01-10'),
        ],
    )
    @patch.object(tasks, 'run_checks')
    def test_wifi_client_check_snooze_schedule(self, mocked_run_checks, *args):
        with freeze_time('2025-01-26'):
            tasks.run_wifi_client_checks()
            mocked_run_checks.assert_not_called()

        with freeze_time('2025-06-15'):
            tasks.run_wifi_client_checks()
            mocked_run_checks.assert_not_called()

        with freeze_time('2025-07-10'):
            tasks.run_wifi_client_checks()
            mocked_run_checks.assert_not_called()

        with freeze_time('2025-08-31'):
            tasks.run_wifi_client_checks()
            mocked_run_checks.assert_not_called()

        with freeze_time('2024-12-30'):
            tasks.run_wifi_client_checks()
            mocked_run_checks.assert_not_called()

        with freeze_time('2025-01-03'):
            tasks.run_wifi_client_checks()
            mocked_run_checks.assert_not_called()

        with freeze_time('2024-12-12'):
            tasks.run_wifi_client_checks()
            mocked_run_checks.assert_called_with(checks=[self._WIFI_CLIENT])
