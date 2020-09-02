from unittest.mock import patch

from django.core.cache import cache
from swapper import load_model

from ..signals import health_status_changed
from ..tasks import trigger_device_checks
from ..utils import get_device_cache_key
from . import DeviceMonitoringTestCase

DeviceMonitoring = load_model('device_monitoring', 'DeviceMonitoring')


class TestRecovery(DeviceMonitoringTestCase):
    """
    Tests ``Device Recovery Detection`` functionality
    """

    def test_device_recovery_cache_key_not_set(self):
        device_monitoring_app = DeviceMonitoring._meta.app_config
        health_status_changed.disconnect(
            device_monitoring_app.manage_device_recovery_cache_key,
            sender=DeviceMonitoring,
            dispatch_uid='recovery_health_status_changed',
        )
        with patch(
            'openwisp_monitoring.device.apps.app_settings.DEVICE_RECOVERY_DETECTION',
            False,
        ):
            device_monitoring_app.device_recovery_detection()
        dm = self._create_device_monitoring()
        cache_key = get_device_cache_key(device=dm.device)
        dm.update_status('critical')
        dm.refresh_from_db()
        self.assertEqual(dm.status, 'critical')
        self.assertEqual(cache.get(cache_key), None)
        device_monitoring_app.device_recovery_detection()

    def test_device_recovery_cache_key_set(self):
        dm = self._create_device_monitoring()
        cache_key = get_device_cache_key(device=dm.device)
        dm.update_status('critical')
        dm.refresh_from_db()
        self.assertEqual(dm.status, 'critical')
        self.assertEqual(cache.get(cache_key), 1)
        dm.update_status('problem')
        dm.refresh_from_db()
        self.assertEqual(dm.status, 'problem')
        self.assertEqual(cache.get(cache_key), None)
        dm.update_status('ok')
        dm.refresh_from_db()
        self.assertEqual(dm.status, 'ok')
        self.assertEqual(cache.get(cache_key), None)

    def test_status_set_ok(self):
        """
        Tests device status is set to ok if no related checks present
        """
        dm = self._create_device_monitoring()
        dm.update_status('critical')
        trigger_device_checks.delay(dm.device.pk)
        dm.refresh_from_db()
        self.assertEqual(dm.status, 'ok')

    def test_status_set_critical(self):
        """
        Tests device status is set to critical if no related checks present
        and recovery=False is passed
        """
        dm = self._create_device_monitoring()
        dm.update_status('critical')
        trigger_device_checks.delay(dm.device.pk, recovery=False)
        dm.refresh_from_db()
        self.assertEqual(dm.status, 'critical')
