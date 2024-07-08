from copy import deepcopy

import django
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.forms import generic_inlineformset_factory
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import datetime, now, timedelta
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
AlertSettings = load_model('monitoring', 'AlertSettings')
DeviceData = load_model('device_monitoring', 'DeviceData')
WifiClient = load_model('device_monitoring', 'WifiClient')
WifiSession = load_model('device_monitoring', 'WifiSession')
User = get_user_model()
Check = load_model('check', 'Check')
# needed for config.geo
Device = load_model('config', 'Device')
DeviceLocation = load_model('geo', 'DeviceLocation')
Location = load_model('geo', 'Location')
# model_name changes if swapped
check_model_name = get_model_name('check', 'Check').lower().replace('.', '-')
metric_model_name = get_model_name('monitoring', 'Metric').lower().replace('.', '-')


class TestAdmin(
    TestWifiClientSessionMixin, TestImportExportMixin, DeviceMonitoringTestCase
):
    """
    Test the additions of openwisp-monitoring to DeviceAdmin
    """

    resources_fields = TestImportExportMixin.resource_fields
    resources_fields.append('monitoring_status')
    app_label = 'config'
    _device_params = {
        'group': '',
        'management_ip': '',
        'model': '',
        'os': '',
        'system': '',
        'notes': '',
        'config-TOTAL_FORMS': '0',
        'config-INITIAL_FORMS': '0',
        'config-MIN_NUM_FORMS': '0',
        'config-MAX_NUM_FORMS': '1',
        # devicelocation
        'devicelocation-TOTAL_FORMS': '0',
        'devicelocation-INITIAL_FORMS': '0',
        'devicelocation-MIN_NUM_FORMS': '0',
        'devicelocation-MAX_NUM_FORMS': '1',
        # deviceconnection
        'deviceconnection_set-TOTAL_FORMS': '0',
        'deviceconnection_set-INITIAL_FORMS': '0',
        'deviceconnection_set-MIN_NUM_FORMS': '0',
        'deviceconnection_set-MAX_NUM_FORMS': '1000',
        # command
        'command_set-TOTAL_FORMS': '0',
        'command_set-INITIAL_FORMS': '0',
        'command_set-MIN_NUM_FORMS': '0',
        'command_set-MAX_NUM_FORMS': '1000',
        # check
        f'{check_model_name}-content_type-object_id-TOTAL_FORMS': '0',
        f'{check_model_name}-content_type-object_id-INITIAL_FORMS': '0',
        f'{check_model_name}-content_type-object_id-MIN_NUM_FORMS': '0',
        f'{check_model_name}-content_type-object_id-MAX_NUM_FORMS': '1000',
    }

    def setUp(self):
        self._login_admin()

    def tearDown(self):
        cache.clear()

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

    def test_wifisession_dashboard_chart_query(self):
        url = reverse('admin:index')
        with self.assertNumQueries(10):
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        device_monitoring_app_label = WifiSession._meta.app_label
        for query in connection.queries:
            if query['sql'] == (
                f'SELECT COUNT("{device_monitoring_app_label}_wifisession"."id") '
                f'AS "active__count" FROM "{device_monitoring_app_label}_wifisession" '
                f'WHERE "{device_monitoring_app_label}_wifisession"."stop_time" IS NULL'
            ):
                break
        else:
            self.fail('WiFiSession dashboard query not found')

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
        data['interfaces'].append(deepcopy(data['interfaces'][0]))
        data['interfaces'][2].update(
            {
                'name': 'wlan2',
                'mac': '44:d1:fa:4b:38:45',
            }
        )
        data['interfaces'][2]['wireless']['mode'] = 'station'
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
        with self.subTest('Wireless client table header is shown'):
            self.assertContains(
                r,
                '<th class="mac">\n\nAssociated client\n\nMAC address\n\n' '</th>',
                html=True,
                count=2,
            )
            self.assertContains(
                r,
                '<th class="mac">\n\nAccess Point\n\nMAC address\n\n' '</th>',
                html=True,
                count=1,
            )
        with self.subTest('Wireless interface properties are shown'):
            self.assertContains(
                r,
                '<div class="form-row">\n<label>Quality:</label>\n'
                '<div class="readonly">\n65 / 70\n</div>\n</div>',
                html=True,
            )
            self.assertContains(
                r,
                '<div class="form-row">\n<label>Bitrate:</label>\n'
                '<div class="readonly">\n1.1 MBits/s\n</div>\n</div>',
                html=True,
            )

    def test_status_data_contains_wifi_version(self):
        data = self._data()
        d = self._create_device(organization=self._create_org())
        url = reverse('admin:config_device_change', args=[d.pk])
        self._post_data(d.id, d.key, data)
        response = self.client.get(url)
        self.assertContains(
            response,
            """
                <div class="readonly">
                    WiFi 4 (802.11n): HT20
                </div>
            """,
            html=True,
        )
        self.assertContains(
            response,
            """
                <div class="readonly">
                    WiFi 5 (802.11ac): VHT80
                </div>
            """,
            html=True,
        )

    def test_status_data_contains_wifi_client_he_vht_ht_unknown(self):
        data = deepcopy(self._data())
        d = self._create_device(organization=self._create_org())
        url = reverse('admin:config_device_change', args=[d.pk])
        wireless_interface = data['interfaces'][0]['wireless']
        client = data['interfaces'][0]['wireless']['clients'][0]

        with self.subTest('Test when htmode is NOHT'):
            wireless_interface.update({'htmode': 'NOHT'})
            self._post_data(d.id, d.key, data)
            response = self.client.get(url)
            # make sure 'he', 'vht' and 'ht' are set to None
            self.assertContains(
                response,
                """
                    <td class="he">
                        <img src="/static/admin/img/icon-unknown.svg">
                    </td>
                    <td class="vht">
                        <img src="/static/admin/img/icon-unknown.svg">
                    </td>
                    <td class="ht">
                        <img src="/static/admin/img/icon-unknown.svg">
                    </td>
                """,
                html=True,
            )

        with self.subTest('Test when htmode is HT and client he and vht are False'):
            wireless_interface.update({'htmode': 'HT40'})
            # both 'he' and 'vht' are False
            self.assertEqual(client['he'], False)
            self.assertEqual(client['vht'], False)
            self._post_data(d.id, d.key, data)
            response = self.client.get(url)
            # make sure 'he' and 'vht' are set to None
            self.assertContains(
                response,
                """
                    <td class="he">
                        <img src="/static/admin/img/icon-unknown.svg">
                    </td>
                    <td class="vht">
                        <img src="/static/admin/img/icon-unknown.svg">
                    </td>
                    <td class="ht">
                        <img src="/static/admin/img/icon-yes.svg">
                    </td>
                """,
                html=True,
            )

        with self.subTest('Test when htmode is VHT and client he is False'):
            wireless_interface.update({'htmode': 'VHT80'})
            client.update({'vht': True})
            self.assertEqual(client['he'], False)
            self.assertEqual(client['vht'], True)
            self._post_data(d.id, d.key, data)
            response = self.client.get(url)
            # make sure only 'he' is set to None
            self.assertContains(
                response,
                """
                    <td class="he">
                        <img src="/static/admin/img/icon-unknown.svg">
                    </td>
                    <td class="vht">
                        <img src="/static/admin/img/icon-yes.svg">
                    </td>
                    <td class="ht">
                        <img src="/static/admin/img/icon-yes.svg">
                    </td>
                """,
                html=True,
            )

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

    def test_device_disabled_organization_admin(self):
        self.create_test_data()
        device = Device.objects.first()
        Check.objects.create(
            name='Ping check',
            check_type=CHECK_CLASSES[0][0],
            content_object=device,
            params={},
        )
        org = device.organization
        org.is_active = False
        org.save()
        url = reverse('admin:config_device_change', args=[device.pk])
        response = self.client.get(url)
        self.assertContains(response, '<h2>Status</h2>')
        self.assertContains(response, '<h2>Charts</h2>')
        self.assertNotContains(response, '<h2>Checks</h2>')
        self.assertNotContains(response, '<h2>AlertSettings</h2>')

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
        self.assertContains(
            r1,
            """
                <a class="bridge-member"
                   href="javascript:scrollToElement('status-if-tap0')">
                    tap0
                </a>
            """,
            html=True,
        )
        self.assertContains(
            r1,
            """
                <a class="bridge-member"
                    href="javascript:scrollToElement('status-if-wlan0')">
                     wlan0
                </a>
            """,
            html=True,
        )
        self.assertContains(
            r1,
            """
                <a class="bridge-member"
                   href="javascript:scrollToElement('status-if-wlan1')">
                    wlan1
                </a>
            """,
            html=True,
        )
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
        ct = f'{check_model_name}-content_type-object_id'
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

    def test_wifisession_inline(self):
        device = self._create_device()
        path = reverse('admin:config_device_change', args=[device.id])

        with self.subTest('Test inline absent when no WiFiSession is present'):
            response = self.client.get(path)
            self.assertNotContains(response, '<h2>WiFi Sessions</h2>')
            self.assertNotContains(response, 'monitoring-wifisession-changelist-url')

        wifi_session = self._create_wifi_session(device=device)

        with self.subTest('Test inline present when WiFiSession is open'):
            response = self.client.get(path)
            self.assertContains(response, '<h2>WiFi Sessions</h2>')
            self.assertContains(response, 'monitoring-wifisession-changelist-url')

        wifi_session.stop_time = now()
        wifi_session.save()

        with self.subTest('Test inline absent when WiFiSession is closed'):
            response = self.client.get(path)
            self.assertNotContains(response, '<h2>WiFi Sessions</h2>')
            self.assertNotContains(response, 'monitoring-wifisession-changelist-url')

    def test_check_alertsetting_inline(self):
        test_user = self._create_user(
            username='test', email='test@inline.com', is_staff=True
        )
        self._create_org_user(is_admin=True, user=test_user)
        device = self._create_device()
        ping_check = Check(
            check_type=CHECK_CLASSES[0][0], content_object=device, params={}
        )
        ping_check.full_clean()
        ping_check.save()
        url = reverse('admin:config_device_change', args=[device.pk])
        metric = self._create_general_metric(
            name='', content_object=device, configuration='ping'
        )
        self._create_alert_settings(metric=metric)
        self.client.force_login(test_user)

        def _add_device_permissions(user):
            test_user.user_permissions.clear()
            self.assertEqual(user.user_permissions.count(), 0)
            device_permissions = Permission.objects.filter(codename__endswith='device')
            # Permissions required to access device page
            test_user.user_permissions.add(*device_permissions),
            self.assertEqual(user.user_permissions.count(), 4)

        def _add_user_permissions(user, permission_query, expected_perm_count):
            user.user_permissions.add(*Permission.objects.filter(**permission_query))
            self.assertEqual(user.user_permissions.count(), expected_perm_count)

        def _assert_check_inline_in_response(response):
            self.assertContains(response, '<h2>Checks</h2>', html=True)
            self.assertContains(response, 'check-content_type-object_id-0-is_active')
            self.assertContains(response, 'check-content_type-object_id-0-check_type')
            self.assertContains(response, 'check-content_type-object_id-0-DELETE')

        def _assert_alertsettings_inline_in_response(response):
            self.assertContains(response, '<h2>Alert Settings</h2>', html=True)
            self.assertContains(response, 'form-row field-name')
            self.assertContains(
                response,
                '<img src="/static/admin/img/icon-yes.svg" alt="True">',
                html=True,
            )
            self.assertContains(response, '<h2>Advanced options</h2>', html=True)
            self.assertContains(
                response,
                'metric-content_type-object_id-0-alertsettings-0-is_active',
            )
            self.assertContains(
                response, '<option value="&lt;" selected>less than</option>'
            )
            self.assertContains(
                response,
                'metric-content_type-object_id-0-alertsettings-0-custom_threshold" value="1"',
            )
            self.assertContains(
                response,
                'metric-content_type-object_id-0-alertsettings-0-custom_tolerance" value="0"',
            )

        with self.subTest(
            'Test when a user does not have permission to access models or inline'
        ):
            _add_device_permissions(test_user)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, '<h2>Checks</h2>', html=True)
            self.assertNotContains(response, '<h2>Alert Settings</h2>', html=True)

        with self.subTest('Test check & alert settings with model permissions'):
            _add_device_permissions(test_user)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            _add_user_permissions(test_user, {'codename__endswith': 'check'}, 8)
            _add_user_permissions(test_user, {'codename__endswith': 'metric'}, 12)
            _add_user_permissions(
                test_user, {'codename__endswith': 'alertsettings'}, 16
            )
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            _assert_check_inline_in_response(response)
            _assert_alertsettings_inline_in_response(response)

        with self.subTest('Test all inline permissions'):
            _add_device_permissions(test_user)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            _add_user_permissions(test_user, {'codename__endswith': 'inline'}, 12)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            _assert_check_inline_in_response(response)
            _assert_alertsettings_inline_in_response(response)

        with self.subTest('Test view inline permissions'):
            _add_device_permissions(test_user)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            _add_user_permissions(
                test_user, {'codename__endswith': 'view_check_inline'}, 5
            )
            _add_user_permissions(
                test_user, {'codename__endswith': 'view_alertsettings_inline'}, 6
            )
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, '<h2>Checks</h2>', html=True)
            self.assertContains(response, 'form-row field-check_type')
            self.assertContains(response, 'form-row field-is_active')
            self.assertContains(response, '<h2>Alert Settings</h2>', html=True)
            self.assertContains(response, 'form-row field-is_healthy djn-form-row-last')
            self.assertContains(
                response,
                '<img src="/static/admin/img/icon-yes.svg" alt="True">',
                html=True,
            )
            self.assertContains(
                response,
                'form-row field-is_active',
            )
            self.assertContains(response, 'form-row field-custom_operator')
            self.assertContains(
                response,
                'form-row field-custom_threshold',
            )
            self.assertContains(
                response,
                'form-row field-custom_tolerance',
            )

    def test_alert_settings_inline_post(self):
        device = self._create_device()
        metric = self._create_general_metric(
            name='', content_object=device, configuration='iperf3'
        )
        url = reverse('admin:config_device_change', args=[device.pk])
        alertsettings = self._create_alert_settings(metric=metric)
        test_inline_params = {
            'name': device.name,
            'organization': str(device.organization.id),
            'mac_address': device.mac_address,
            'key': device.key,
            # metric & alertsettings
            f'{metric_model_name}-content_type-object_id-TOTAL_FORMS': '1',
            f'{metric_model_name}-content_type-object_id-INITIAL_FORMS': '1',
            f'{metric_model_name}-content_type-object_id-MIN_NUM_FORMS': '0',
            f'{metric_model_name}-content_type-object_id-MAX_NUM_FORMS': '1000',
            f'{metric_model_name}-content_type-object_id-0-field_name': 'iperf3_result',
            f'{metric_model_name}-content_type-object_id-0-id': str(metric.id),
            f'{metric_model_name}-content_type-object_id-0-alertsettings-TOTAL_FORMS': '1',
            f'{metric_model_name}-content_type-object_id-0-alertsettings-INITIAL_FORMS': '0',
            f'{metric_model_name}-content_type-object_id-0-alertsettings-MIN_NUM_FORMS': '0',
            f'{metric_model_name}-content_type-object_id-0-alertsettings-MAX_NUM_FORMS': '1',
            f'{metric_model_name}-content_type-object_id-0-alertsettings-0-is_active': 'on',
            f'{metric_model_name}-content_type-object_id-0-alertsettings-0-custom_operator': '<',
            f'{metric_model_name}-content_type-object_id-0-alertsettings-0-custom_threshold': '9',
            f'{metric_model_name}-content_type-object_id-0-alertsettings-0-custom_tolerance': '1800',
            f'{metric_model_name}-content_type-object_id-0-alertsettings-0-id': '',
            f'{metric_model_name}-content_type-object_id-0-alertsettings-0-metric': '',
        }
        # General metrics (clients & traffic) & Iperf3 are present
        self.assertEqual(Metric.objects.count(), 3)
        self.assertEqual(AlertSettings.objects.count(), 1)

        def _reset_alertsettings_inline():
            AlertSettings.objects.all().delete()

        # Delete AlertSettings objects before any subTests
        _reset_alertsettings_inline()
        # Delete all Metrics other than 'iperf3' before any subTests
        Metric.objects.exclude(configuration='iperf3').delete()

        def _assert_alertsettings_inline(response, operator, threshold, tolerance):
            self.assertEqual(response.status_code, 302)
            self.assertEqual(Metric.objects.count(), 1)
            self.assertEqual(AlertSettings.objects.count(), 1)
            alertsettings = AlertSettings.objects.first()
            self.assertEqual(alertsettings.operator, operator)
            self.assertEqual(alertsettings.threshold, threshold)
            self.assertEqual(alertsettings.tolerance, tolerance)

        with self.subTest('Test alert settings inline when all fields are provided'):
            self._device_params.update(test_inline_params)
            response = self.client.post(url, self._device_params)
            _assert_alertsettings_inline(response, '<', 9, 1800)
        _reset_alertsettings_inline()

        with self.subTest(
            'Test alert settings inline when partial fields are provided'
        ):
            test_inline_default_1 = {
                f'{metric_model_name}-content_type-object_id-0-alertsettings-0-custom_operator': '>',
                f'{metric_model_name}-content_type-object_id-0-alertsettings-0-custom_threshold': '',
                f'{metric_model_name}-content_type-object_id-0-alertsettings-0-custom_tolerance': '',
            }
            self._device_params.update(test_inline_default_1)
            response = self.client.post(url, self._device_params)
            # 'threshold' and 'tolerance' are set to their default values
            _assert_alertsettings_inline(response, '>', 1, 0)
            _reset_alertsettings_inline()

            test_inline_default_2 = {
                f'{metric_model_name}-content_type-object_id-0-alertsettings-0-custom_operator': '',
                f'{metric_model_name}-content_type-object_id-0-alertsettings-0-custom_threshold': '18',
                f'{metric_model_name}-content_type-object_id-0-alertsettings-0-custom_tolerance': '99',
            }
            self._device_params.update(test_inline_default_2)
            response = self.client.post(url, self._device_params)
            # 'operator' are set to their default values
            _assert_alertsettings_inline(response, '<', 18, 99)
        _reset_alertsettings_inline()

        with self.subTest('Test alert settings inline when all fields are absent'):
            test_inline_params_present = {
                f'{metric_model_name}-content_type-object_id-0-alertsettings-0-custom_operator': '<',
                f'{metric_model_name}-content_type-object_id-0-alertsettings-0-custom_threshold': '99',
                f'{metric_model_name}-content_type-object_id-0-alertsettings-0-custom_tolerance': '1880',
            }
            self._device_params.update(test_inline_params_present)
            response = self.client.post(url, self._device_params)
            _assert_alertsettings_inline(response, '<', 99, 1880)

            alertsettings = AlertSettings.objects.first()
            metric = Metric.objects.first()

            test_inline_params_absent = {
                f'{metric_model_name}-content_type-object_id-INITIAL_FORMS': '1',
                f'{metric_model_name}-content_type-object_id-0-id': str(metric.id),
                f'{metric_model_name}-content_type-object_id-0-field_name': 'iperf3_result',
                f'{metric_model_name}-content_type-object_id-0-alertsettings-INITIAL_FORMS': '1',
                f'{metric_model_name}-content_type-object_id-0-alertsettings-0-id': str(
                    alertsettings.id
                ),
                f'{metric_model_name}-content_type-object_id-0-alertsettings-0-metric': str(
                    metric.id
                ),
                f'{metric_model_name}-content_type-object_id-0-alertsettings-0-custom_operator': '',
                f'{metric_model_name}-content_type-object_id-0-alertsettings-0-custom_threshold': '',
                f'{metric_model_name}-content_type-object_id-0-alertsettings-0-custom_tolerance': '',
            }
            self._device_params.update(test_inline_params_absent)
            response = self.client.post(url, self._device_params)
            # If all the fields are empty, then it deletes the AlertSettings object
            # to prevent the default value from being used as a fallback
            self.assertEqual(response.status_code, 302)
            self.assertEqual(Metric.objects.count(), 1)
            self.assertEqual(AlertSettings.objects.count(), 0)

    def test_device_admin_recover_button_visibility(self):
        self._create_device(organization=self._create_org())
        url = reverse('admin:config_device_changelist')
        response = self.client.get(url)
        self.assertContains(
            response,
            """
                <li>
                    <a href="/admin/config/device/recover/" class="recoverlink">Recover deleted Devices</a>
                </li>
            """,
            html=True,
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
            'monitoring/css/leaflet.fullscreen.css',
            'monitoring/css/netjsongraph.css',
            'leaflet/leaflet.css',
            'monitoring/js/lib/netjsongraph.min.js',
            'monitoring/js/lib/leaflet.fullscreen.min.js',
            'monitoring/js/device-map.js',
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

    wifi_session_app_label = WifiSession._meta.app_label
    wifi_session_model_name = WifiSession._meta.model_name

    def setUp(self):
        admin = self._create_admin()
        self.client.force_login(admin)

    def test_changelist_filters_and_multitenancy(self):
        url = reverse(
            f'admin:{self.wifi_session_app_label}_{self.wifi_session_model_name}_changelist'
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
            # Filter by device pk
            response = self.client.get(url, {'device': str(org2_device.pk)})
            _assert_org2_wifi_session_in_response(
                response, org1_interface_data, org2_interface_data
            )

        with self.subTest('Test multitenancy'):
            administrator = self._create_administrator(organizations=[org2])
            self.client.force_login(administrator)
            response = self.client.get(url)
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

    def test_dashboard_wifi_session_chart(self):
        org1 = self._create_org(name='org1', slug='org1')
        org1_device = self._create_device(organization=org1)
        self._create_wifi_session(device=org1_device)
        org2 = self._create_org(name='org2', slug='org2')
        administrator = self._create_administrator([org2])
        self.client.force_login(administrator)
        response = self.client.get(reverse('admin:index'))
        self.assertEqual(response.status_code, 200)
        self.assertDictEqual(
            response.context['dashboard_charts'][13]['query_params'],
            {'labels': [], 'values': []},
        )

    def test_wifi_client_he_vht_ht_unknown(self):
        test_wifi_client = self._create_wifi_client(he=None, vht=None, ht=None)
        test_wifi_session = self._create_wifi_session(wifi_client=test_wifi_client)
        device = Device.objects.all().first()

        with self.subTest('Test device wifi session inline'):
            url = reverse('admin:config_device_change', args=[device.id])
            response = self.client.get(url)
            self.assertContains(
                response,
                """
                    <td class="field-he">
                        <p><img src="/static/admin/img/icon-unknown.svg"></p>
                    </td>
                    <td class="field-vht">
                        <p><img src="/static/admin/img/icon-unknown.svg"></p>
                    </td>
                    <td class="field-ht">
                        <p><img src="/static/admin/img/icon-unknown.svg"></p>
                    </td>
                """,
                html=True,
            )
        with self.subTest('Test device wifi session list'):
            url = reverse(
                f'admin:{self.wifi_session_app_label}_{self.wifi_session_model_name}_changelist'
            )
            response = self.client.get(url)
            self.assertContains(
                response,
                """
                    <td class="field-he">
                        <img src="/static/admin/img/icon-unknown.svg">
                    </td>
                    <td class="field-vht">
                        <img src="/static/admin/img/icon-unknown.svg">
                    </td>
                    <td class="field-ht">
                        <img src="/static/admin/img/icon-unknown.svg">
                    </td>
                """,
                html=True,
            )
        with self.subTest('Test device wifi session change'):
            url = reverse(
                f'admin:{self.wifi_session_app_label}_{self.wifi_session_model_name}_change',
                args=[test_wifi_session.id],
            )
            response = self.client.get(url)
            self.assertContains(
                response,
                """
                    <div class="form-row field-he">
                        <div>
                            {start_div}
                                <label>WiFi 6 (802.11ax):</label>
                                    <div class="readonly">
                                        <img src="/static/admin/img/icon-unknown.svg">
                                    </div>
                            {end_div}
                        </div>
                    </div>
                    <div class="form-row field-vht">
                        <div>
                            {start_div}<label>WiFi 5 (802.11ac):</label>
                                <div class="readonly">
                                    <img src="/static/admin/img/icon-unknown.svg">
                                </div>
                            {end_div}
                        </div>
                    </div>
                    <div class="form-row field-ht">
                        <div>
                            {start_div}<label>WiFi 4 (802.11n):</label>
                                <div class="readonly">
                                    <img src="/static/admin/img/icon-unknown.svg">
                                </div>
                            {end_div}
                        </div>
                    </div>
                """.format(
                    # TODO: Remove this when dropping support for Django 3.2 and 4.0
                    start_div='<div class="flex-container">'
                    if django.VERSION >= (4, 2)
                    else '',
                    end_div='</div>' if django.VERSION >= (4, 2) else '',
                ),
                html=True,
            )

    def test_wifi_session_stop_time_formatting(self):
        start_time = datetime.strptime('2023-8-24 17:08:00', '%Y-%m-%d %H:%M:%S')
        stop_time = datetime.strptime('2023-8-24 19:46:00', '%Y-%m-%d %H:%M:%S')
        session = self._create_wifi_session(stop_time=stop_time)
        # WifiSession.start_time has "auto_now" set to True.
        # To overwrite the current date, we set the start_time explicitly
        WifiSession.objects.update(start_time=start_time)
        url = reverse(
            f'admin:{self.wifi_session_app_label}_{self.wifi_session_model_name}_change',
            args=(session.id,),
        )
        response = self.client.get(url)
        self.assertContains(
            response,
            (
                '<label>Start time:</label>\n\n'
                '<div class="readonly">Aug. 24, 2023, 5:08 p.m.</div>'
            ),
            html=True,
        )
        self.assertContains(
            response,
            (
                '<label>Stop time:</label>\n\n'
                '<div class="readonly">Aug. 24, 2023, 7:46 p.m.</div>'
            ),
            html=True,
        )
