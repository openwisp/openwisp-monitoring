from django.test import TransactionTestCase
from swapper import load_model

from ...device.tests import TestDeviceMonitoringMixin
from .. import settings
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
    _WIFI_CLIENT = settings.CHECK_CLASSES[3][0]

    def test_store_result(self):
        def _assert_wifi_client_metric(key):
            metric = metric_qs.get(key=key)
            self.assertEqual(metric.content_object, device)
            points = self._read_metric(metric, limit=None)
            self.assertEqual(len(points), 1)
            self.assertEqual(points[0]['clients'], 3)
            return metric

        device_data = self.create_test_data(no_resources=True, assertions=False)
        device = Device.objects.get(id=device_data.id)
        metric_qs = Metric.objects.filter(
            key__in=['max_wifi_clients', 'min_wifi_clients']
        )
        alert_settings_qs = AlertSettings.objects.filter(
            metric__key__in=['max_wifi_clients', 'min_wifi_clients']
        )
        # check created automatically by AUTO_WIFI_CLIENT_CHECK
        self.assertEqual(Check.objects.count(), 4)
        self.assertEqual(metric_qs.count(), 0)
        self.assertEqual(alert_settings_qs.count(), 0)
        check = Check.objects.filter(check_type=self._WIFI_CLIENT).first()
        result = check.perform_check()
        self.assertEqual(result, 3)
        self.assertEqual(metric_qs.count(), 2)
        self.assertEqual(alert_settings_qs.count(), 2)

        max_wifi_clients = _assert_wifi_client_metric('max_wifi_clients')
        self.assertEqual(max_wifi_clients.alertsettings.operator, '>')
        min_wifi_clients = _assert_wifi_client_metric('min_wifi_clients')
        self.assertEqual(min_wifi_clients.alertsettings.operator, '<')

    def test_device_no_wifi_client(self):
        device = self._create_device()
        check = Check.objects.filter(check_type=self._WIFI_CLIENT).first()
        result = check.perform_check()
        self.assertEqual(result, 0)
        max_wifi_client = Metric.objects.filter(
            key='max_wifi_clients', object_id=device.id
        ).first()
        points = self._read_metric(max_wifi_client, limit=None)
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0]['clients'], 0)
        min_wifi_client = Metric.objects.filter(
            key='min_wifi_clients', object_id=device.id
        ).first()
        points = self._read_metric(min_wifi_client, limit=None)
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0]['clients'], 0)
