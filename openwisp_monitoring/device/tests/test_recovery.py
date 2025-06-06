import json
from unittest.mock import patch

from django.core.cache import cache
from swapper import load_model

from ..signals import health_status_changed
from ..tasks import trigger_device_checks, trigger_device_critical_checks
from ..utils import get_device_cache_key
from . import DeviceMonitoringTestCase, DeviceMonitoringTransactionTestcase

DeviceMonitoring = load_model("device_monitoring", "DeviceMonitoring")
DeviceData = load_model("device_monitoring", "DeviceData")
Device = load_model("config", "Device")
Check = load_model("check", "Check")


class TestRecovery(DeviceMonitoringTestCase):
    """Tests ``Device Recovery Detection`` functionality"""

    def test_device_recovery_cache_key_not_set(self):
        device_monitoring_app = DeviceMonitoring._meta.app_config
        health_status_changed.disconnect(
            device_monitoring_app.manage_device_recovery_cache_key,
            sender=DeviceMonitoring,
            dispatch_uid="recovery_health_status_changed",
        )
        with patch(
            "openwisp_monitoring.device.apps.app_settings.DEVICE_RECOVERY_DETECTION",
            False,
        ):
            device_monitoring_app.device_recovery_detection()
        dm = self._create_device_monitoring()
        cache_key = get_device_cache_key(device=dm.device)
        dm.update_status("critical")
        dm.refresh_from_db()
        self.assertEqual(dm.status, "critical")
        self.assertEqual(cache.get(cache_key), None)
        device_monitoring_app.device_recovery_detection()

    def test_device_recovery_cache_key_set(self):
        dm = self._create_device_monitoring()
        cache_key = get_device_cache_key(device=dm.device)
        dm.update_status("critical")
        dm.refresh_from_db()
        self.assertEqual(dm.status, "critical")
        self.assertEqual(cache.get(cache_key), 1)
        dm.update_status("problem")
        dm.refresh_from_db()
        self.assertEqual(dm.status, "problem")
        self.assertEqual(cache.get(cache_key), None)
        dm.update_status("ok")
        dm.refresh_from_db()
        self.assertEqual(dm.status, "ok")
        self.assertEqual(cache.get(cache_key), None)

    def test_status_set_ok(self):
        """Tests device status is set to ok if no related checks present"""
        dm = self._create_device_monitoring()
        dm.update_status("critical")
        trigger_device_critical_checks.delay(dm.device.pk)
        dm.refresh_from_db()
        self.assertEqual(dm.status, "ok")

    def test_status_set_critical(self):
        """Tests device status is set to critical if no related checks present and recovery=False is passed"""
        dm = self._create_device_monitoring()
        dm.update_status("critical")
        trigger_device_critical_checks.delay(dm.device.pk, recovery=False)
        dm.refresh_from_db()
        self.assertEqual(dm.status, "critical")

    @patch("openwisp_monitoring.device.tasks.trigger_device_critical_checks")
    def test_trigger_device_checks(self, mocked_task):
        dm = self._create_device_monitoring()
        trigger_device_checks.delay(dm.device.pk)
        mocked_task.assert_called_once_with(dm.device.pk, True)


class TestRecoveryTransaction(DeviceMonitoringTransactionTestcase):
    @patch("openwisp_monitoring.device.tasks.perform_check.delay")
    def test_metrics_received_trigger_device_recovery_checks(self, mocked_task):
        device = self._create_config(organization=self._get_org()).device
        device_monitoring = device.monitoring
        netjson = json.dumps(self._data())
        url = self._url(device.pk, key=device.key)

        with self.subTest('Test checks are not triggered if device is "ok"'):
            device_monitoring.update_status("ok")

            response = self.client.post(
                url,
                data=netjson,
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200)
            mocked_task.assert_not_called()

        mocked_task.reset_mock()
        with self.subTest(
            'Ensure checks are not triggered if device status is "problem"'
        ):
            device_monitoring.update_status("problem")
            response = self.client.post(
                url,
                data=netjson,
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200)
            mocked_task.assert_not_called()

        mocked_task.reset_mock()
        with self.subTest('Ensure checks are triggered if device is "critical"'):
            device_monitoring.update_status("critical")
            response = self.client.post(
                url,
                data=netjson,
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200)
            critical_checks = device_monitoring.get_critical_checks()
            self.assertEqual(mocked_task.call_count, len(critical_checks))
            # Verify that only critical checks are triggered
            # Get the check types from the mocked task calls
            triggered_check_types = list(
                Check.objects.filter(
                    id__in=[call[0][0] for call in mocked_task.call_args_list]
                ).values_list("check_type", flat=True)
            )
            self.assertListEqual(sorted(triggered_check_types), sorted(critical_checks))
            device_monitoring.refresh_from_db()
            self.assertEqual(device_monitoring.status, "problem")
