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
    _WIFI_CLIENTS = settings.CHECK_CLASSES[3][0]

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
        self.assertEqual(Check.objects.count(), 4)
        self.assertEqual(metric_qs.count(), 0)
        self.assertEqual(alert_settings_qs.count(), 0)
        check = Check.objects.filter(check_type=self._WIFI_CLIENTS).first()
        result = check.perform_check()
        self.assertEqual(result, 3)
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
        self.assertEqual(result, 0)
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
