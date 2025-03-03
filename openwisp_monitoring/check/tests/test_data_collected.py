from unittest.mock import patch

from django.test import TransactionTestCase
from django.utils import timezone
from freezegun import freeze_time
from swapper import load_model

from ...device.tests import TestDeviceMonitoringMixin
from ...device.utils import SHORT_RP
from .. import settings as app_settings
from .. import tasks
from . import AutoDataCollectedCheck

Chart = load_model('monitoring', 'Chart')
AlertSettings = load_model('monitoring', 'AlertSettings')
Metric = load_model('monitoring', 'Metric')
Check = load_model('check', 'Check')
Device = load_model('config', 'Device')


class TestDataCollected(
    AutoDataCollectedCheck,
    TestDeviceMonitoringMixin,
    TransactionTestCase,
):
    _DATA_COLLECTED = app_settings.CHECK_CLASSES[4][0]

    def _run_data_collected_check(self):
        tasks.run_checks(checks=[self._DATA_COLLECTED])

    def _create_device(self, monitoring_status='ok', *args, **kwargs):
        device = super()._create_device(*args, **kwargs)
        device.monitoring.status = monitoring_status
        device.monitoring.save()
        return device

    def test_store_result(self):
        device_data = self.create_test_data(no_resources=True, assertions=False)
        device = Device.objects.get(id=device_data.id)
        metric_qs = Metric.objects.filter(key__in=['data_collected'])
        alert_settings_qs = AlertSettings.objects.filter(
            metric__key__in=['data_collected']
        )
        # check created automatically by AUTO_DATA_COLLECTED_CHECK
        self.assertEqual(metric_qs.count(), 0)
        self.assertEqual(alert_settings_qs.count(), 0)
        check = Check.objects.filter(check_type=self._DATA_COLLECTED).first()
        result = check.perform_check()
        self.assertEqual(result, {'data_collected': 1})
        self.assertEqual(metric_qs.count(), 1)
        self.assertEqual(alert_settings_qs.count(), 1)

        data_collected = metric_qs.get(key='data_collected')
        self.assertEqual(data_collected.content_object, device)
        points = self._read_metric(data_collected, retention_policy=SHORT_RP)
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0]['data_collected'], 1)

    def test_device_no_passive_metrics(self):
        device = self._create_device()
        check = Check.objects.filter(check_type=self._DATA_COLLECTED).first()
        result = check.perform_check()
        self.assertEqual(result, {'data_collected': 0})
        data_collected = Metric.objects.filter(
            key='data_collected', object_id=device.id
        ).first()
        points = self._read_metric(data_collected, retention_policy=SHORT_RP)
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0]['data_collected'], 0)

    def test_device_offline(self):
        with freeze_time(
            timezone.now()
            - timezone.timedelta(minutes=app_settings.DATA_COLLECTED_CHECK_INTERVAL + 1)
        ):
            self.create_test_data(no_resources=True, assertions=False)
        check = Check.objects.filter(check_type=self._DATA_COLLECTED).first()
        result = check.perform_check()
        self.assertEqual(result, {'data_collected': 0})
        data_collected = Metric.objects.filter(key='data_collected').first()
        points = self._read_metric(data_collected, retention_policy=SHORT_RP)
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0]['data_collected'], 0)

    def test_device_critical_no_alert(self):
        with freeze_time(
            timezone.now()
            - timezone.timedelta(minutes=app_settings.DATA_COLLECTED_CHECK_INTERVAL + 1)
        ):
            device_data = self.create_test_data(no_resources=True, assertions=False)
            self._run_data_collected_check()
        device = Device.objects.get(id=device_data.id)
        device.monitoring.update_status('critical')
        check = Check.objects.filter(check_type=self._DATA_COLLECTED).first()
        with patch.object(Metric, 'write') as write:
            result = check.perform_check()
            self.assertEqual(result, {'data_collected': 0})
        self.assertEqual(write.call_args.kwargs['send_alert'], False)
