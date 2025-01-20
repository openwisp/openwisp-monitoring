from datetime import datetime
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from freezegun import freeze_time

from .. import settings as app_settings
from .. import tasks


class TestRunWifiClientChecks(TestCase):
    _WIFI_CLIENTS = app_settings.CHECK_CLASSES[3][0]

    @patch.object(tasks, 'run_checks')
    def test_wifi_clients_check_snooze_schedule_empty(self, mocked_run_checks):
        tasks.run_wifi_clients_checks()
        mocked_run_checks.assert_called_with(checks=[self._WIFI_CLIENTS])

    @patch.object(
        tasks,
        'WIFI_CLIENTS_CHECK_SNOOZE_SCHEDULE',
        [
            ('01-26', '01-26'),
            ('06-15', '08-31'),
            ('12-25', '01-10'),
            ('22:00', '06:00'),
            ('12-13 18:00', '12-13 19:00'),
        ],
    )
    @patch.object(tasks, 'run_checks')
    def test_wifi_clients_check_snooze_schedule(self, mocked_run_checks, *args):
        tz = timezone.get_current_timezone()
        with freeze_time(datetime(2025, 1, 26, tzinfo=tz)):
            tasks.run_wifi_clients_checks()
            mocked_run_checks.assert_not_called()

        with freeze_time(datetime(2025, 6, 15, 8, tzinfo=tz)):
            tasks.run_wifi_clients_checks()
            mocked_run_checks.assert_not_called()

        with freeze_time(datetime(2025, 7, 10, 2, tzinfo=tz)):
            tasks.run_wifi_clients_checks()
            mocked_run_checks.assert_not_called()

        with freeze_time(datetime(2025, 8, 31, tzinfo=tz)):
            tasks.run_wifi_clients_checks()
            mocked_run_checks.assert_not_called()

        with freeze_time(datetime(2024, 12, 30, tzinfo=tz)):
            tasks.run_wifi_clients_checks()
            mocked_run_checks.assert_not_called()

        with freeze_time(datetime(2024, 12, 30, 18, tzinfo=tz)):
            tasks.run_wifi_clients_checks()
            mocked_run_checks.assert_not_called()

        with freeze_time(datetime(2025, 1, 3, tzinfo=tz)):
            tasks.run_wifi_clients_checks()
            mocked_run_checks.assert_not_called()

        with freeze_time(datetime(2024, 12, 12, 21, tzinfo=tz)):
            tasks.run_wifi_clients_checks()
            mocked_run_checks.assert_not_called()

        with freeze_time(datetime(2024, 12, 12, 0, tzinfo=tz)):
            tasks.run_wifi_clients_checks()
            mocked_run_checks.assert_not_called()

        with freeze_time(datetime(2024, 12, 12, 5, tzinfo=tz)):
            tasks.run_wifi_clients_checks()
            mocked_run_checks.assert_not_called()

        with freeze_time(datetime(2024, 12, 13, 18, 30, tzinfo=tz)):
            tasks.run_wifi_clients_checks()
            mocked_run_checks.assert_not_called()

        with freeze_time(datetime(2024, 12, 14, 18, tzinfo=tz)):
            tasks.run_wifi_clients_checks()
            mocked_run_checks.assert_called_with(checks=[self._WIFI_CLIENTS])
