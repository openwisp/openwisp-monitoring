from datetime import datetime
from unittest.mock import patch

from django.contrib.contenttypes.models import ContentType
from django.test import TransactionTestCase
from django.utils import timezone
from freezegun import freeze_time
from swapper import load_model

from ...device.tests import TestDeviceMonitoringMixin
from .. import settings as app_settings
from .. import tasks
from ..classes import WifiClients
from . import AutoWifiClientCheck

Chart = load_model('monitoring', 'Chart')
AlertSettings = load_model('monitoring', 'AlertSettings')
Metric = load_model('monitoring', 'Metric')
Check = load_model('check', 'Check')
Device = load_model('config', 'Device')


class TestWifiClient(
    AutoWifiClientCheck,
    TestDeviceMonitoringMixin,
    TransactionTestCase,
):
    _WIFI_CLIENTS = app_settings.CHECK_CLASSES[3][0]

    def _run_wifi_clients_checks(self):
        tasks.run_checks(checks=[self._WIFI_CLIENTS])

    def _create_device(self, monitoring_status='ok', *args, **kwargs):
        device = super()._create_device(*args, **kwargs)
        device.monitoring.status = monitoring_status
        device.monitoring.save()
        return device

    def test_store_result(self):
        def _assert_wifi_clients_metric(key):
            metric = metric_qs.get(key=key)
            self.assertEqual(metric.content_object, device)
            points = self._read_metric(metric, limit=None)
            self.assertEqual(len(points), 1)
            self.assertEqual(points[0]['clients'], 3)
            return metric

        device_data = self.create_test_data(no_resources=True, assertions=False)
        device = Device.objects.get(id=device_data.id)
        metric_qs = Metric.objects.filter(
            key__in=['wifi_clients_max', 'wifi_clients_min']
        )
        alert_settings_qs = AlertSettings.objects.filter(
            metric__key__in=['wifi_clients_max', 'wifi_clients_min']
        )
        # check created automatically by AUTO_WIFI_CLIENTS_CHECK
        self.assertEqual(Check.objects.count(), 5)
        self.assertEqual(metric_qs.count(), 0)
        self.assertEqual(alert_settings_qs.count(), 0)
        check = Check.objects.filter(check_type=self._WIFI_CLIENTS).first()
        result = check.perform_check()
        self.assertEqual(result, {'wifi_clients_min': 3, 'wifi_clients_max': 3})
        self.assertEqual(metric_qs.count(), 2)
        self.assertEqual(alert_settings_qs.count(), 2)

        wifi_clients_max = _assert_wifi_clients_metric('wifi_clients_max')
        self.assertEqual(wifi_clients_max.alertsettings.operator, '>')
        wifi_clients_min = _assert_wifi_clients_metric('wifi_clients_min')
        self.assertEqual(wifi_clients_min.alertsettings.operator, '<')

    def test_device_no_wifi_client(self):
        device = self._create_device()
        check = Check.objects.filter(check_type=self._WIFI_CLIENTS).first()
        result = check.perform_check()
        self.assertEqual(result, {'wifi_clients_min': 0, 'wifi_clients_max': 0})
        wifi_clients_max = Metric.objects.filter(
            key='wifi_clients_max', object_id=device.id
        ).first()
        points = self._read_metric(wifi_clients_max, limit=None)
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0]['clients'], 0)
        wifi_clients_min = Metric.objects.filter(
            key='wifi_clients_min', object_id=device.id
        ).first()
        points = self._read_metric(wifi_clients_min, limit=None)
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0]['clients'], 0)

    @patch.object(WifiClients, '_check_wifi_clients_min')
    @patch.object(WifiClients, '_check_wifi_clients_max')
    def test_check_skipped_unknown_status(self, max_mocked, min_mocked):
        device = self._create_device(monitoring_status='unknown')
        check = Check.objects.filter(check_type=self._WIFI_CLIENTS).first()

        with self.subTest('Test check skipped when device status is unknown'):
            result = check.perform_check()
            self.assertEqual(result, None)
            max_mocked.assert_not_called()
            min_mocked.assert_not_called()

        with self.subTest('Test check skipped when device status is critical'):
            device.monitoring.status = 'critical'
            device.monitoring.save()
            result = check.perform_check()
            self.assertEqual(result, None)
            max_mocked.assert_not_called()
            min_mocked.assert_not_called()

    @patch.object(
        app_settings,
        'WIFI_CLIENTS_CHECK_SNOOZE_SCHEDULE',
        [],
    )
    @patch.object(WifiClients, 'check')
    def test_wifi_clients_check_snooze_schedule_empty(self, mocked_check, *args):
        self._create_device()
        self._run_wifi_clients_checks()
        mocked_check.assert_called()

    @patch.object(
        app_settings,
        'WIFI_CLIENTS_CHECK_SNOOZE_SCHEDULE',
        [
            ('01-26', '01-26'),
            ('06-15', '08-31'),
            ('12-25', '01-10'),
            ('22:00', '06:00'),
            ('12-13 18:00', '12-13 19:00'),
        ],
    )
    @patch.object(WifiClients, 'check')
    def test_wifi_clients_check_snooze_schedule(self, mocked_check, *args):
        Check.objects.create(
            name='WiFi Clients',
            check_type=self._WIFI_CLIENTS,
            content_type=ContentType.objects.get_for_model(Device),
            object_id='e82e7924-ca3d-4f77-97ab-62bc1de2b919',
        )
        tz = timezone.get_current_timezone()
        with freeze_time(datetime(2025, 1, 26, tzinfo=tz)):
            self._run_wifi_clients_checks()
            mocked_check.assert_not_called()

        with freeze_time(datetime(2025, 6, 15, 8, tzinfo=tz)):
            self._run_wifi_clients_checks()
            mocked_check.assert_not_called()

        with freeze_time(datetime(2025, 7, 10, 2, tzinfo=tz)):
            self._run_wifi_clients_checks()
            mocked_check.assert_not_called()

        with freeze_time(datetime(2025, 8, 31, tzinfo=tz)):
            self._run_wifi_clients_checks()
            mocked_check.assert_not_called()

        with freeze_time(datetime(2024, 12, 30, tzinfo=tz)):
            self._run_wifi_clients_checks()
            mocked_check.assert_not_called()

        with freeze_time(datetime(2024, 12, 30, 18, tzinfo=tz)):
            self._run_wifi_clients_checks()
            mocked_check.assert_not_called()

        with freeze_time(datetime(2025, 1, 3, tzinfo=tz)):
            self._run_wifi_clients_checks()
            mocked_check.assert_not_called()

        with freeze_time(datetime(2024, 12, 12, 22, 0, tzinfo=tz)):
            self._run_wifi_clients_checks()
            mocked_check.assert_not_called()

        with freeze_time(datetime(2024, 12, 12, 0, 0, tzinfo=tz)):
            self._run_wifi_clients_checks()
            mocked_check.assert_not_called()

        with freeze_time(datetime(2024, 12, 12, 5, 0, tzinfo=tz)):
            self._run_wifi_clients_checks()
            mocked_check.assert_not_called()

        with freeze_time(datetime(2024, 12, 13, 18, 30, tzinfo=tz)):
            self._run_wifi_clients_checks()
            mocked_check.assert_not_called()

        with freeze_time(datetime(2024, 12, 14, 18, tzinfo=tz)):
            self._run_wifi_clients_checks()
            mocked_check.assert_called()
