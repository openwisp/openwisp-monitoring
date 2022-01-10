from django.contrib.auth import get_user_model
from django.contrib.contenttypes.forms import generic_inlineformset_factory
from django.urls import reverse
from django.utils.timezone import now
from swapper import get_model_name, load_model

from openwisp_controller.geo.tests.utils import TestGeoMixin

from ...check.settings import CHECK_CLASSES
from ..admin import CheckInline, CheckInlineFormSet
from . import DeviceMonitoringTestCase

Chart = load_model('monitoring', 'Chart')
Metric = load_model('monitoring', 'Metric')
DeviceData = load_model('device_monitoring', 'DeviceData')
User = get_user_model()
Check = load_model('check', 'Check')
# needed for config.geo
Device = load_model('config', 'Device')
DeviceLocation = load_model('geo', 'DeviceLocation')
Location = load_model('geo', 'Location')


class TestAdmin(DeviceMonitoringTestCase):
    """
    Test the additions of openwisp-monitoring to DeviceAdmin
    """

    def _login_admin(self):
        u = User.objects.create_superuser('admin', 'admin', 'test@test.com')
        self.client.force_login(u)

    def test_device_admin(self):
        dd = self.create_test_data()
        check = Check.objects.create(
            name='Ping check',
            check_type=CHECK_CLASSES[0][0],
            content_object=dd,
            params={},
        )
        url = reverse('admin:config_device_change', args=[dd.pk])
        self._login_admin()
        response = self.client.get(url)
        self.assertContains(response, '<h2>Status</h2>')
        self.assertContains(response, '<h2>Charts</h2>')
        self.assertContains(response, '<h2>Checks</h2>')
        self.assertContains(response, 'Storage')
        self.assertContains(response, 'CPU')
        self.assertContains(response, 'RAM status')
        self.assertContains(response, 'AlertSettings')
        self.assertContains(response, 'Is healthy')
        self.assertContains(response, 'http://testserver/api')
        self.assertContains(response, check.name)
        self.assertContains(response, check.params)

    def test_dashboard_map_on_index(self):
        url = reverse('admin:index')
        self._login_admin()
        response = self.client.get(url)
        self.assertContains(response, "geoJsonUrl: \'http://testserver/api")
        self.assertContains(response, "locationDeviceUrl: \'http://testserver/api")

    def test_status_data(self):
        d = self._create_device(organization=self._create_org())
        data = self._data()
        data.update(
            {
                "dhcp_leases": [
                    {
                        "expiry": 1586943200,
                        "mac": "f2:f1:3e:56:d2:77",
                        "ip": "192.168.66.196",
                        "client_name": "MyPhone1",
                        "client_id": "01:20:f4:78:19:3b:38",
                    },
                ],
                "neighbors": [
                    {
                        "mac": "44:D1:FA:4B:00:02",
                        "ip": "fe80::9683:c4ff:fe02:c2bf",
                        "interface": "eth2",
                        "state": "REACHABLE",
                    }
                ],
            }
        )
        self._post_data(d.id, d.key, data)
        url = reverse('admin:config_device_change', args=[d.pk])
        self._login_admin()
        r = self.client.get(url)
        with self.subTest('DHCP lease MAC is shown'):
            self.assertContains(r, 'f2:f1:3e:56:d2:77')
        with self.subTest('DHCP lease IP is shown'):
            self.assertContains(r, '192.168.66.196')
        with self.subTest('Neighbor MAC is shown'):
            self.assertContains(r, '44:D1:FA:4B:00:02')
        with self.subTest('Neighbor IP is shown'):
            self.assertContains(r, 'fe80::9683:c4ff:fe02:c2bf')

    def test_no_device_data(self):
        d = self._create_device(organization=self._create_org())
        url = reverse('admin:config_device_change', args=[d.pk])
        self._login_admin()
        r = self.client.get(url)
        self.assertNotContains(r, '<h2>Status</h2>')
        self.assertNotContains(r, 'AlertSettings')

    def test_device_add_view(self):
        self._login_admin()
        url = reverse('admin:config_device_add')
        r = self.client.get(url)
        self.assertNotContains(r, 'AlertSettings')
        self.assertContains(r, '<h2>Configuration</h2>')
        self.assertContains(r, '<h2>Map</h2>')
        self.assertContains(r, '<h2>Credentials</h2>')
        self.assertContains(r, '<h2>Checks</h2>')

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
        dd = self.create_test_data(no_resources=True)
        url = reverse('admin:config_device_change', args=[dd.id])
        r1 = self.client.get(url, follow=True)
        self.assertEqual(r1.status_code, 200)
        self.assertContains(r1, '00:ee:ad:34:f5:3b')

    def test_interface_properties_admin(self):
        self._login_admin()
        dd = self.create_test_data(no_resources=True)
        url = reverse('admin:config_device_change', args=[dd.id])
        r1 = self.client.get(url, follow=True)
        self.assertEqual(r1.status_code, 200)
        self.assertContains(r1, '44:d1:fa:4b:38:44')
        self.assertContains(r1, 'Transmit Queue Length')
        self.assertContains(r1, 'Up')
        self.assertContains(r1, 'Multicast')
        self.assertContains(r1, 'MTU')

    def test_interface_bridge_admin(self):
        self._login_admin()
        d = self._create_device(organization=self._create_org())
        dd = DeviceData(name='test-device', pk=d.pk)
        data = self._data()
        del data['resources']
        self._post_data(
            d.id,
            d.key,
            {
                'type': 'DeviceMonitoring',
                'interfaces': [
                    {
                        'name': 'br-lan',
                        'type': 'bridge',
                        'bridge_members': ['tap0', 'wlan0', 'wlan1'],
                        'stp': True,
                    }
                ],
            },
        )
        url = reverse('admin:config_device_change', args=[dd.id])
        r1 = self.client.get(url, follow=True)
        self.assertEqual(r1.status_code, 200)
        self.assertContains(r1, 'Bridge Members')
        self.assertContains(r1, 'tap0, wlan0, wlan1')
        self.assertContains(r1, 'Spanning Tree Protocol')

    def test_interface_mobile_admin(self):
        self._login_admin()
        d = self._create_device(organization=self._create_org())
        self._post_data(
            d.id,
            d.key,
            {
                'type': 'DeviceMonitoring',
                'interfaces': [
                    {
                        'name': 'mobile0',
                        'mac': '00:00:00:00:00:00',
                        'mtu': 1900,
                        'multicast': True,
                        'txqueuelen': 1000,
                        'type': 'modem-manager',
                        'up': True,
                        'mobile': {
                            'connection_status': 'connected',
                            'imei': '300000001234567',
                            'manufacturer': 'Sierra Wireless, Incorporated',
                            'model': 'MC7430',
                            'operator_code': '50502',
                            'operator_name': 'YES OPTUS',
                            'power_status': 'on',
                            'signal': {
                                'lte': {'rsrp': -75, 'rsrq': -8, 'rssi': -51, 'snr': 13}
                            },
                        },
                    }
                ],
            },
        )
        url = reverse('admin:config_device_change', args=[d.id])
        r1 = self.client.get(url, follow=True)
        self.assertEqual(r1.status_code, 200)
        self.assertContains(r1, 'Signal Strength (LTE)')
        self.assertContains(r1, 'Signal Power (LTE)')
        self.assertContains(r1, 'Signal Quality (LTE)')
        self.assertContains(r1, 'Signal to noise ratio (LTE)')

    def test_uuid_bug(self):
        dd = self.create_test_data(no_resources=True)
        uuid = str(dd.pk).replace('-', '')
        url = reverse('admin:config_device_change', args=[uuid])
        self._login_admin()
        r = self.client.get(url)
        self.assertContains(r, '<h2>Status</h2>')

    def test_check_inline_formset(self):
        d = self._create_device(organization=self._create_org())
        check_inline_formset = generic_inlineformset_factory(
            model=Check, form=CheckInline.form, formset=CheckInlineFormSet
        )
        # model_name changes if swapped
        model_name = get_model_name('check', 'Check').lower().replace('.', '-')
        ct = f'{model_name}-content_type-object_id'
        data = {
            f'{ct}-TOTAL_FORMS': '1',
            f'{ct}-INITIAL_FORMS': '0',
            f'{ct}-MAX_NUM_FORMS': '0',
            f'{ct}-0-name': 'Ping Check',
            f'{ct}-0-check_type': CHECK_CLASSES[0][0],
            f'{ct}-0-params': '{}',
            f'{ct}-0-is_active': True,
            f'{ct}-0-created': now(),
            f'{ct}-0-modified': now(),
        }
        formset = check_inline_formset(data)
        formset.instance = d
        self.assertTrue(formset.is_valid())
        self.assertEqual(formset.errors, [{}])
        self.assertEqual(formset.non_form_errors(), [])
        form = formset.forms[0]
        form.cleaned_data = data
        form.save(commit=True)
        self.assertEqual(Check.objects.count(), 1)
        c = Check.objects.first()
        self.assertEqual(c.name, 'Ping Check')
        self.assertEqual(c.content_object, d)

    def test_health_checks_list(self):
        dd = self.create_test_data()
        url = reverse('admin:config_device_change', args=[dd.pk])
        self._login_admin()
        r = self.client.get(url)
        self.assertNotContains(r, '<label>Health checks:</label>')
        m = Metric.objects.filter(configuration='disk').first()
        m.write(m.alertsettings.threshold + 0.1)
        m.refresh_from_db()
        self.assertEqual(m.is_healthy, False)
        self.assertEqual(m.is_healthy_tolerant, False)
        self.assertEqual(dd.monitoring.status, 'problem')
        r = self.client.get(url)
        self.assertContains(r, '<label>Health checks:</label>')
        # Clients and Traffic metrics
        interface_metrics = dd.metrics.filter(alertsettings__isnull=True)
        interface_metric = interface_metrics.first()
        interface_metric.is_healthy = True
        interface_metric.save()
        for metric in interface_metrics:
            self.assertNotContains(r, f'{metric.name}</li>')
        other_metrics = dd.metrics.filter(alertsettings__isnull=False)
        for metric in other_metrics:
            health = 'yes' if metric.is_healthy else 'no'
            self.assertContains(
                r,
                f'<li><img src="/static/admin/img/icon-{health}.svg" '
                f'alt="health"> {metric.name}</li>',
            )


class TestAdminDashboard(TestGeoMixin, DeviceMonitoringTestCase):
    location_model = Location
    object_location_model = DeviceLocation
    object_model = Device

    def test_dashboard(self):
        admin = User.objects.create_superuser('admin', 'admin', 'test@test.com')
        self.client.force_login(admin)
        self._create_object_location()
        response = self.client.get(reverse('admin:index'))
        static_files = [
            'monitoring/css/device-map.css',
            'leaflet/leaflet.css',
            'monitoring/css/leaflet.fullscreen.css',
            'monitoring/js/device-map.js',
            'leaflet/leaflet.js',
            'leaflet/leaflet.extras.js',
            'monitoring/js/leaflet.fullscreen.min.js',
        ]
        for static_file in static_files:
            self.assertContains(response, static_file)
        self.assertContains(response, 'Monitoring Status')
        self.assertContains(response, '#267126')
