from copy import deepcopy

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.forms import generic_inlineformset_factory
from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import now, timedelta
from freezegun import freeze_time
from swapper import get_model_name, load_model

from openwisp_controller.config.tests.test_admin import TestImportExportMixin
from openwisp_controller.config.tests.utils import CreateDeviceGroupMixin
from openwisp_controller.geo.tests.utils import TestGeoMixin
from openwisp_users.tests.utils import TestMultitenantAdminMixin

from ...check.settings import CHECK_CLASSES
from ..admin import CheckInline, CheckInlineFormSet
from . import DeviceMonitoringTestCase, TestWifiClientSessionMixin

Chart = load_model('monitoring', 'Chart')
Metric = load_model('monitoring', 'Metric')
DeviceData = load_model('device_monitoring', 'DeviceData')
WifiClient = load_model('device_monitoring', 'WifiClient')
WifiSession = load_model('device_monitoring', 'WifiSession')
User = get_user_model()
Check = load_model('check', 'Check')
# needed for config.geo
Device = load_model('config', 'Device')
DeviceLocation = load_model('geo', 'DeviceLocation')
Location = load_model('geo', 'Location')


class TestAdmin(TestImportExportMixin, DeviceMonitoringTestCase):
    """
    Test the additions of openwisp-monitoring to DeviceAdmin
    """

    resources_fields = TestImportExportMixin.resource_fields
    resources_fields.append('monitoring__status')
    app_label = 'config'

    def setUp(self):
        self._login_admin()

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
        r = self.client.get(url)
        self.assertNotContains(r, '<h2>Status</h2>')
        self.assertNotContains(r, 'AlertSettings')

    def test_device_add_view(self):
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
        self.client.get(url)

    def test_wifi_clients_admin(self):
        dd = self.create_test_data(no_resources=True)
        url = reverse('admin:config_device_change', args=[dd.id])
        r1 = self.client.get(url, follow=True)
        self.assertEqual(r1.status_code, 200)
        self.assertContains(r1, '00:ee:ad:34:f5:3b')

    def test_interface_properties_admin(self):
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


class TestWifiSessionAdmin(
    CreateDeviceGroupMixin,
    TestMultitenantAdminMixin,
    TestWifiClientSessionMixin,
    TestCase,
):
    def setUp(self):
        admin = self._create_admin()
        self.client.force_login(admin)

    def test_changelist_filters_and_multitenancy(self):
        url = reverse(
            'admin:{app_label}_{model_name}_changelist'.format(
                app_label=WifiSession._meta.app_label,
                model_name=WifiSession._meta.model_name,
            )
        )
        org1 = self._create_org(name='org1', slug='org1')
        org1_device_group = self._create_device_group(
            name='Org1 Routers', organization=org1
        )
        org1_device = self._create_device(
            name='org1-device', organization=org1, group=org1_device_group
        )
        org1_dd = self._create_device_data(device=org1_device)
        org1_interface_data = deepcopy(self._sample_data['interfaces'][0])
        org1_interface_data['name'] = 'org1_wlan0'
        org1_interface_data['wireless']['ssid'] = 'org1_wifi'
        org1_interface_data['wireless']['clients'][0]['mac'] = '00:ee:ad:34:f5:3b'

        org2 = self._create_org(name='org1', slug='org2')
        org2_device_group = self._create_device_group(
            name='Org2 Routers', organization=org2
        )
        org2_device = self._create_device(
            name='org2-device', organization=org2, group=org2_device_group
        )
        org2_dd = self._create_device_data(device=org2_device)
        org2_interface_data = deepcopy(self._sample_data['interfaces'][0])
        org2_interface_data['name'] = 'org2_wlan0'
        org2_interface_data['wireless']['ssid'] = 'org2_wifi'
        org2_interface_data['wireless']['clients'][0]['mac'] = '00:ee:ad:34:f5:3c'

        self._save_device_data(
            device_data=org1_dd,
            data={'type': 'DeviceMonitoring', 'interfaces': [org1_interface_data]},
        )
        self.assertEqual(WifiClient.objects.count(), 1)
        self.assertEqual(
            WifiSession.objects.filter(device__organization=org1).count(), 1
        )
        WifiSession.objects.filter(device__organization=org1).update(stop_time=now())

        with freeze_time(now() - timedelta(days=2)):
            self._save_device_data(
                device_data=org2_dd,
                data={'type': 'DeviceMonitoring', 'interfaces': [org2_interface_data]},
            )
        self.assertEqual(WifiClient.objects.count(), 2)
        self.assertEqual(
            WifiSession.objects.filter(device__organization=org2).count(), 1
        )

        def _assert_org2_wifi_session_in_response(
            response, org1_interface_data, org2_interface_data
        ):
            self.assertContains(
                response, '<p class="paginator">\n\n1 WiFi Session\n\n\n</p>'
            )
            self.assertContains(
                response,
                '<td class="field-ssid">{}</td>'.format(
                    org2_interface_data['wireless']['ssid']
                ),
            )
            self.assertContains(
                response, org2_interface_data['wireless']['clients'][0]['mac']
            )
            self.assertNotContains(
                response,
                '<td class="field-ssid">{}</td>'.format(
                    org1_interface_data['wireless']['ssid']
                ),
            )
            self.assertNotContains(
                response, org1_interface_data['wireless']['clients'][0]['mac']
            )

        with self.subTest('Test without filters'):
            response = self.client.get(url)
            self.assertContains(
                response, '<p class="paginator">\n\n2 WiFi Sessions\n\n\n</p>'
            )

        with self.subTest('Test start_time filter'):
            response = self.client.get(
                url, {'start_time__lte': now() - timedelta(days=1)}
            )
            _assert_org2_wifi_session_in_response(
                response, org1_interface_data, org2_interface_data
            )

        with self.subTest('Test stop_time filter'):
            response = self.client.get(url, {'stop_time__isnull': 'True'})
            _assert_org2_wifi_session_in_response(
                response, org1_interface_data, org2_interface_data
            )

        with self.subTest('Test organization filter'):
            response = self.client.get(
                url, {'device__organization__id__exact': str(org2.pk)}
            )
            _assert_org2_wifi_session_in_response(
                response, org1_interface_data, org2_interface_data
            )

        with self.subTest('Test device_group filter'):
            response = self.client.get(
                url, {'device__group__id__exact': str(org2_device_group.pk)}
            )
            _assert_org2_wifi_session_in_response(
                response, org1_interface_data, org2_interface_data
            )

        with self.subTest('Test device filter'):
            # Filter by device name
            response = self.client.get(url, {'device': org2_device.name})
            _assert_org2_wifi_session_in_response(
                response, org1_interface_data, org2_interface_data
            )
            # Filter by device pk
            response = self.client.get(url, {'device': str(org2_device.pk)})
            _assert_org2_wifi_session_in_response(
                response, org1_interface_data, org2_interface_data
            )

        with self.subTest('Test multitenancy'):
            administrator = self._create_administrator(organizations=[org2])
            self.client.force_login(administrator)
            _assert_org2_wifi_session_in_response(
                response, org1_interface_data, org2_interface_data
            )

    def test_wifi_session_chart_on_index(self):
        url = reverse('admin:index')
        self._create_wifi_session()
        response = self.client.get(url)
        self.assertContains(response, 'Currently Active WiFi Sessions')
        self.assertContains(response, 'Open WiFi session list')

    def test_deleting_device_with_wifisessions(self):
        device_data = self._save_device_data()
        path = reverse('admin:config_device_delete', args=[device_data.pk])
        response = self.client.post(path, {'post': 'yes'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Device.objects.count(), 0)
