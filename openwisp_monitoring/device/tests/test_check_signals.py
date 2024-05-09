from django.test import TestCase
from swapper import load_model

from openwisp_monitoring.device.models import CHECK_CLASSES

Check = load_model('check', 'Check')
Device = load_model('config', 'Device')
DeviceMonitoring = load_model('device_monitoring', 'DeviceMonitoring')


class TestCheckSignals(TestCase):
    def setUp(self):
        self.device = self._create_device(organization=self._create_org())
        self.ping_check = Check.objects.create(
            name='Ping Check',
            check_type=CHECK_CLASSES[0][0],
            content_object=self.device,
            params={},
        )

    def test_check_signals(self):
        with self.subTest('Test disabling a critical check'):
            self.ping_check.is_active = False
            self.ping_check.save()
            self.device.refresh_from_db()
            self.assertEqual(self.device.monitoring.status, 'unknown')

        with self.subTest('Test saving an active critical check'):
            self.ping_check.is_active = True
            self.ping_check.save()
            self.device.refresh_from_db()
            self.assertNotEqual(self.device.monitoring.status, 'unknown')

        with self.subTest('Test saving a non-critical check'):
            non_critical_check = Check.objects.create(
                name='Non-Critical Check',
                check_type=CHECK_CLASSES[1][0],
                content_object=self.device,
                params={},
            )
            non_critical_check.save()
            self.device.refresh_from_db()
            self.assertNotEqual(self.device.monitoring.status, 'unknown')

        with self.subTest('Test deleting a critical check'):
            self.ping_check.delete()
            self.device.refresh_from_db()
            self.assertEqual(self.device.monitoring.status, 'unknown')
