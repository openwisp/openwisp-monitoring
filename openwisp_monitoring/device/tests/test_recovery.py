from unittest.mock import patch

from django.core.cache import cache
from django.urls import reverse
from swapper import load_model

from ...check.classes import Ping
from ...check.tasks import auto_create_ping
from ...check.tests import _FPING_REACHABLE
from ..signals import health_status_changed
from ..tasks import trigger_device_checks
from ..utils import get_device_recovery_cache_key
from . import DeviceMonitoringTestCase

Check = load_model('check', 'Check')
DeviceMonitoring = load_model('device_monitoring', 'DeviceMonitoring')
Metric = load_model('monitoring', 'Metric')


class TestRecovery(DeviceMonitoringTestCase):
    """
    Tests ``Device Recovery Detection`` functionality
    """

    def _create_device_monitoring(self):
        d = self._create_device(organization=self._create_org())
        dm = d.monitoring
        dm.status = 'ok'
        dm.save()
        return dm

    @patch.object(Ping, '_command', return_value=_FPING_REACHABLE)
    def test_trigger_device_recovery_task(self, mocked_method):
        d = self._create_device(organization=self._create_org())
        d.management_ip = '10.40.0.5'
        d.save()
        data = self._data()
        # Creation of resources, clients and traffic metrics can be avoided here
        # as they are not involved. This speeds up the test by reducing requests made.
        del data['resources']
        del data['interfaces']
        auto_create_ping.delay(
            model='device', app_label='config', object_id=str(d.pk),
        )
        check = Check.objects.first()
        check.perform_check()
        self.assertEqual(Metric.objects.count(), 1)
        d.monitoring.update_status('critical')
        url = reverse('monitoring:api_device_metric', args=[d.pk.hex])
        url = '{0}?key={1}'.format(url, d.key)
        with patch.object(Check, 'perform_check') as mock:
            self._post_data(d.id, d.key, data)
        mock.assert_called_once()

    def test_device_recovery_cache_key_not_set(self):
        device_monitoring_app = DeviceMonitoring._meta.app_config
        health_status_changed.disconnect(
            device_monitoring_app.manage_device_recovery_cache_key,
            sender=DeviceMonitoring,
        )
        with patch(
            'openwisp_monitoring.device.apps.app_settings.DEVICE_RECOVERY_DETECTION',
            False,
        ):
            device_monitoring_app.device_recovery_detection()
        dm = self._create_device_monitoring()
        cache_key = get_device_recovery_cache_key(device=dm.device)
        dm.update_status('critical')
        dm.refresh_from_db()
        self.assertEqual(dm.status, 'critical')
        self.assertEqual(cache.get(cache_key), None)
        device_monitoring_app.device_recovery_detection()

    def test_device_recovery_cache_key_set(self):
        dm = self._create_device_monitoring()
        cache_key = get_device_recovery_cache_key(device=dm.device)
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

    # Tests device status is set to ok if no related checks present
    def test_status_set_ok(self):
        dm = self._create_device_monitoring()
        dm.update_status('critical')
        trigger_device_checks.delay(dm.device.pk)
        dm.refresh_from_db()
        self.assertEqual(dm.status, 'ok')
