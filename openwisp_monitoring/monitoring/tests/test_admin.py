from copy import deepcopy

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import now, timedelta
from freezegun import freeze_time
from swapper import load_model

from openwisp_controller.config.tests.utils import CreateDeviceGroupMixin
from openwisp_users.tests.utils import TestMultitenantAdminMixin

from . import TestMonitoringMixin, TestWifiClientSessionMixin

WifiClient = load_model('monitoring', 'WifiClient')
DeviceData = load_model('device_monitoring', 'DeviceData')
WifiSession = load_model('monitoring', 'WifiSession')


class TestAdmin(TestMonitoringMixin, TestCase):
    def _login_admin(self):
        User = get_user_model()
        u = User.objects.create_superuser('admin', 'admin', 'test@test.com')
        self.client.force_login(u)

    def test_metric_admin(self):
        m = self._create_general_metric()
        url = reverse('admin:monitoring_metric_change', args=[m.pk])
        self._login_admin()
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

    def test_alert_settings_inline(self):
        m = self._create_general_metric(configuration='ping')
        alert_s = self._create_alert_settings(metric=m)
        self.assertIsNone(alert_s.custom_operator)
        self.assertIsNone(alert_s.custom_threshold)
        self.assertIsNone(alert_s.custom_tolerance)
        url = reverse('admin:monitoring_metric_change', args=[m.pk])
        self._login_admin()
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, '<option value="&lt;" selected>less than</option>')
        self.assertContains(r, 'name="alertsettings-0-custom_threshold" value="1"')
        self.assertContains(r, 'name="alertsettings-0-custom_tolerance" value="0"')

    def test_admin_menu_groups(self):
        # Test menu group (openwisp-utils menu group) for Metric and Check models
        self._login_admin()
        response = self.client.get(reverse('admin:index'))
        with self.subTest('test menu group link for check model'):
            url = reverse('admin:check_check_changelist')
            self.assertContains(response, f'class="mg-link" href="{url}"')
        with self.subTest('test menu group link for metric model'):
            url = reverse('admin:monitoring_metric_changelist')
            self.assertContains(response, f'class="mg-link" href="{url}"')
        with self.subTest('test "monitoring" group is registered'):
            self.assertContains(
                response,
                '<div class="mg-dropdown-label">Monitoring </div>',
                html=True,
            )


class TestWifiSessionAdmin(
    TestWifiClientSessionMixin,
    CreateDeviceGroupMixin,
    TestMultitenantAdminMixin,
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
