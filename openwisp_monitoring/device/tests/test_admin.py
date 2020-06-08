from django.contrib.auth import get_user_model
from django.urls import reverse
from swapper import load_model

from . import DeviceMonitoringTestCase

Graph = load_model('monitoring', 'Graph')
Metric = load_model('monitoring', 'Metric')
DeviceData = load_model('device_monitoring', 'DeviceData')


class TestAdmin(DeviceMonitoringTestCase):
    """
    Test the additions of openwisp-monitoring to DeviceAdmin
    """

    def _login_admin(self):
        User = get_user_model()
        u = User.objects.create_superuser('admin', 'admin', 'test@test.com')
        self.client.force_login(u)

    def test_device_admin(self):
        dd = self._create_multiple_measurements()
        url = reverse('admin:config_device_change', args=[dd.pk])
        self._login_admin()
        r = self.client.get(url)
        self.assertContains(r, 'Device Status')
        self.assertContains(r, 'Monitoring Graph')

    def test_no_device_data(self):
        d = self._create_device(organization=self._create_org())
        url = reverse('admin:config_device_change', args=[d.pk])
        self._login_admin()
        r = self.client.get(url)
        self.assertNotContains(r, 'Device Status')

    def test_remove_invalid_interface(self):
        d = self._create_device(organization=self._create_org())
        dd = DeviceData(name='test-device', pk=d.pk)
        self._post_data(
            d.id,
            d.key,
            {'type': 'DeviceMonitoring', 'interfaces': [{'name': 'br-lan'}]},
        )
        url = reverse('admin:config_device_change', args=[dd.pk])
        self._login_admin()
        self.client.get(url)

    def test_wifi_clients_admin(self):
        self._login_admin()
        d = self._create_device(organization=self._create_org())
        data = self._data()
        r = self._post_data(d.id, d.key, data)
        url = reverse('admin:config_device_change', args=[d.id])
        r1 = self.client.get(url, follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r1.status_code, 200)
        self.assertContains(r1, '00:ee:ad:34:f5:3b')
