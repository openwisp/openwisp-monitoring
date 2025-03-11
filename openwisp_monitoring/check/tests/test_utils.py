from unittest.mock import patch

from django.core import management
from django.core.checks import Error
from django.test import TestCase, TransactionTestCase
from swapper import load_model

from ...device.tests import TestDeviceMonitoringMixin
from .. import settings as app_settings
from ..checks import check_wifi_clients_snooze_schedule
from ..classes import Ping
from ..tasks import perform_check
from ..utils import run_checks_async
from . import _FPING_REACHABLE

Check = load_model('check', 'Check')


class TestUtils(TestDeviceMonitoringMixin, TransactionTestCase):
    _PING = app_settings.CHECK_CLASSES[0][0]

    def _create_check(self):
        device = self._create_device(organization=self._create_org())
        device.last_ip = '10.40.0.1'
        device.save()
        # check is automatically created via django signal

    @patch.object(Ping, '_command', return_value=_FPING_REACHABLE)
    def test_run_checks_async_success(self, mocked_method):
        self._create_check()
        run_checks_async()

    @patch.object(Ping, '_command', return_value=_FPING_REACHABLE)
    def test_management_command(self, mocked_method):
        self._create_check()
        management.call_command('run_checks')

    @patch('logging.Logger.warning')
    def test_perform_check_task_resiliency(self, mock):
        check = Check(name='Test check')
        perform_check.delay(check.pk)
        mock.assert_called_with(f'The check with uuid {check.pk} has been deleted')


class TestCheckWifiClientsSnoozeSchedule(TestCase):
    def setUp(self):
        self.setting_name = 'OPENWISP_MONITORING_WIFI_CLIENTS_CHECK_SNOOZE_SCHEDULE'

    @patch.object(app_settings, 'WIFI_CLIENTS_CHECK_SNOOZE_SCHEDULE', 'invalid_format')
    def test_invalid_schedule_format(self):
        errors = check_wifi_clients_snooze_schedule(None)
        expected_error = Error(
            'Invalid schedule format',
            hint='Schedule must be a list of date-time ranges',
            obj=self.setting_name,
        )
        self.assertIn(expected_error, errors)

    @patch.object(
        app_settings, 'WIFI_CLIENTS_CHECK_SNOOZE_SCHEDULE', [('invalid_entry',)]
    )
    def test_invalid_schedule_entry_format(self):
        errors = check_wifi_clients_snooze_schedule(None)
        expected_error = Error(
            'Invalid schedule entry format: (\'invalid_entry\',)',
            hint='Each schedule entry must be a pair of start and end times',
            obj=self.setting_name,
        )
        self.assertIn(expected_error, errors)

    @patch.object(
        app_settings, 'WIFI_CLIENTS_CHECK_SNOOZE_SCHEDULE', [('invalid_time', '12:00')]
    )
    def test_invalid_date_time_format(self):
        errors = check_wifi_clients_snooze_schedule(None)
        expected_error = Error(
            'Invalid date-time format: (\'invalid_time\', \'12:00\')',
            hint='Use format "MM-DD HH:MM", "MM-DD", or "HH:MM"',
            obj=self.setting_name,
        )
        self.assertIn(expected_error, errors)

    @patch.object(app_settings, 'WIFI_CLIENTS_CHECK_SNOOZE_SCHEDULE', [(11, 12)])
    def test_invalid_time_format(self):
        errors = check_wifi_clients_snooze_schedule(None)
        expected_error = Error(
            'Invalid time format: (11, 12)',
            hint='Use format "MM-DD HH:MM", "MM-DD", or "HH:MM"',
            obj=self.setting_name,
        )
        self.assertIn(expected_error, errors)

    @patch.object(
        app_settings, 'WIFI_CLIENTS_CHECK_SNOOZE_SCHEDULE', [('12:00', '01-01')]
    )
    def test_inconsistent_format(self):
        errors = check_wifi_clients_snooze_schedule(None)
        expected_error = Error(
            'Inconsistent format: (\'12:00\', \'01-01\')',
            hint='Both start and end must be in the same format (either both time or both date)',
            obj=self.setting_name,
        )
        self.assertIn(expected_error, errors)

    @patch.object(
        app_settings, 'WIFI_CLIENTS_CHECK_SNOOZE_SCHEDULE', [('12:00', '13:00')]
    )
    def test_valid_time_format(self):
        errors = check_wifi_clients_snooze_schedule(None)
        self.assertEqual(errors, [])

    @patch.object(
        app_settings, 'WIFI_CLIENTS_CHECK_SNOOZE_SCHEDULE', [('01-01', '01-02')]
    )
    def test_valid_date_format(self):
        errors = check_wifi_clients_snooze_schedule(None)
        self.assertEqual(errors, [])

    @patch.object(
        app_settings,
        'WIFI_CLIENTS_CHECK_SNOOZE_SCHEDULE',
        [('01-01 12:00', '01-01 13:00')],
    )
    def test_valid_date_time_format(self):
        errors = check_wifi_clients_snooze_schedule(None)
        self.assertEqual(errors, [])
