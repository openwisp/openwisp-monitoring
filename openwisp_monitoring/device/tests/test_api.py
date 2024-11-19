import json
from datetime import datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token
from swapper import load_model

from openwisp_controller.config.tests.utils import CreateDeviceGroupMixin
from openwisp_controller.geo.tests.utils import TestGeoMixin
from openwisp_users.tests.test_api import AuthenticationMixin
from openwisp_users.tests.utils import TestMultitenantAdminMixin
from openwisp_utils.tests import capture_any_output, catch_signal

from ... import settings as monitoring_settings
from ...monitoring.signals import post_metric_write, pre_metric_write
from ..api.serializers import WifiSessionSerializer
from ..signals import device_metrics_received
from . import DeviceMonitoringTestCase, TestWifiClientSessionMixin

start_time = timezone.now()
User = get_user_model()
Chart = load_model('monitoring', 'Chart')
Metric = load_model('monitoring', 'Metric')
DeviceData = load_model('device_monitoring', 'DeviceData')
# needed for config.geo
Device = load_model('config', 'Device')
DeviceLocation = load_model('geo', 'DeviceLocation')
FloorPlan = load_model('geo', 'FloorPlan')
Location = load_model('geo', 'Location')
WifiClient = load_model('device_monitoring', 'WifiClient')
WifiSession = load_model('device_monitoring', 'WifiSession')
Group = load_model('openwisp_users', 'Group')


class TestDeviceApi(AuthenticationMixin, TestGeoMixin, DeviceMonitoringTestCase):
    """Tests API (device metric collection)."""

    location_model = Location
    object_location_model = DeviceLocation
    object_model = Device
    floorplan_model = FloorPlan
    # Exclude general metrics from the query
    metric_queryset = Metric.objects.exclude(object_id=None)
    # Exclude general charts from the query
    chart_queryset = Chart.objects.exclude(metric__object_id=None)
    _RESPONSE_KEYS = [
        'id',
        'name',
        'organization',
        'group',
        'mac_address',
        'key',
        'last_ip',
        'management_ip',
        'model',
        'os',
        'system',
        'notes',
        'config',
        'monitoring',
        'created',
        'modified',
        'charts',
        'x',
    ]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Populate the ContentType cache to avoid queries during test
        ContentType.objects.get_for_model(Device)

    def setUp(self):
        self._login_admin()

    def tearDown(self):
        super().tearDown()
        cache.clear()

    def _login_admin(self):
        u = User.objects.create_superuser('admin', 'admin', 'test@test.com')
        self.client.force_login(u)

    def _assert_device_info(self, device=None, data=None):
        self.assertEqual(data['id'], str(device.pk))
        self.assertEqual(data['name'], device.name)
        self.assertEqual(data['organization'], device.organization.pk)
        self.assertEqual(data['group'], device.group)
        self.assertEqual(data['mac_address'], device.mac_address)
        self.assertEqual(data['key'], device.key)
        self.assertEqual(data['last_ip'], device.last_ip)
        self.assertEqual(data['management_ip'], device.management_ip)
        self.assertEqual(data['model'], device.model)
        self.assertEqual(data['os'], device.os)
        self.assertEqual(data['system'], device.system)
        self.assertEqual(data['notes'], device.notes)
        self.assertIsNone(data['config'])

    def _assert_device_metrics_info(self, data=None, detail=True, charts=True):
        self.assertIn('monitoring', data)
        self.assertIn('status', data['monitoring'])
        if charts:
            self.assertEqual(len(list(data['charts'])), 7)
        if detail:
            self.assertIn('related_metrics', data['monitoring'])
            metrics = list(data['monitoring']['related_metrics'])
            self.assertEqual(metrics[0]['name'], 'CPU usage')
            self.assertEqual(metrics[0]['is_healthy'], True)
            self.assertEqual(metrics[1]['name'], 'Disk usage')
            self.assertEqual(metrics[1]['is_healthy'], True)
            self.assertEqual(metrics[2]['name'], 'Memory usage')
            self.assertEqual(metrics[2]['is_healthy'], True)
            self.assertEqual(metrics[3]['name'], 'wlan0 traffic')
            self.assertEqual(metrics[3]['is_healthy'], None)
            self.assertEqual(metrics[4]['name'], 'wlan0 wifi clients')
            self.assertEqual(metrics[4]['is_healthy'], None)
            self.assertEqual(metrics[5]['name'], 'wlan1 traffic')
            self.assertEqual(metrics[5]['is_healthy'], None)
            self.assertEqual(metrics[6]['name'], 'wlan1 wifi clients')
            self.assertEqual(metrics[6]['is_healthy'], None)

    def test_404(self):
        r = self._post_data(self.device_model().pk, '123', self._data())
        self.assertEqual(r.status_code, 404)

    def test_403(self):
        o = self._create_org()
        d = self._create_device(organization=o)
        r = self.client.post(self._url(d.pk))
        self.assertEqual(r.status_code, 403)
        r = self._post_data(d.id, 'WRONG', self._data())
        self.assertEqual(r.status_code, 403)

    def test_400(self):
        o = self._create_org()
        d = self._create_device(organization=o)
        r = self._post_data(d.id, d.key, {'interfaces': []})
        self.assertEqual(r.status_code, 400)
        r = self._post_data(d.id, d.key, {'interfaces': []})
        self.assertEqual(r.status_code, 400)
        r = self._post_data(
            d.id, d.key, {'type': 'DeviceMonitoring'}, time='23-08-2021 06:25:45'
        )
        self.assertEqual(r.status_code, 400)
        r = self._post_data(
            d.id, d.key, {'type': 'DeviceMonitoring', 'interfaces': [{}]}
        )
        self.assertEqual(r.status_code, 400)

    def test_200_none(self):
        o = self._create_org()
        d = self._create_device(organization=o)
        data = {'type': 'DeviceMonitoring', 'interfaces': []}
        with self.assertNumQueries(4):
            r = self._post_data(d.id, d.key, data)
        self.assertEqual(r.status_code, 200)
        # Add 1 for general metric and chart
        self.assertEqual(self.metric_queryset.count(), 0)
        self.assertEqual(self.chart_queryset.count(), 0)
        data = {'type': 'DeviceMonitoring'}
        with self.assertNumQueries(2):
            r = self._post_data(d.id, d.key, data)
        self.assertEqual(r.status_code, 200)
        # Add 1 for general metric and chart
        self.assertEqual(self.metric_queryset.count(), 0)
        self.assertEqual(self.chart_queryset.count(), 0)
        d.delete(check_deactivated=False)
        r = self._post_data(d.id, d.key, data)
        self.assertEqual(r.status_code, 404)

    def test_200_create(self):
        self.create_test_data(no_resources=True)

    @patch('openwisp_monitoring.device.tasks.write_device_metrics.delay')
    def test_background_write(self, mocked_task):
        device = self._create_device(organization=self._create_org())
        data = self._data()
        r = self._post_data(device.id, device.key, data)
        self.assertEqual(r.status_code, 200)
        mocked_task.assert_called_once()

    def test_200_traffic_counter_incremented(self):
        dd = self.create_test_data(no_resources=True)
        d = self.device_model.objects.first()
        data2 = self._data()
        # creation of resources metrics can be avoided here as it is not involved
        # this speeds up the test by reducing requests made
        del data2['resources']
        data2['interfaces'][0]['statistics']['rx_bytes'] = 983
        data2['interfaces'][0]['statistics']['tx_bytes'] = 1567
        data2['interfaces'][1]['statistics']['rx_bytes'] = 2983
        data2['interfaces'][1]['statistics']['tx_bytes'] = 4567
        r = self._post_data(d.id, d.key, data2)
        self.assertEqual(r.status_code, 200)
        self.assertDataDict(dd.data, data2)
        # Add 1 for general metric and chart
        self.assertEqual(self.metric_queryset.count(), 4)
        self.assertEqual(self.chart_queryset.count(), 4)
        if_dict = {'wlan0': data2['interfaces'][0], 'wlan1': data2['interfaces'][1]}
        for ifname in ['wlan0', 'wlan1']:
            iface = if_dict[ifname]
            m = self.metric_queryset.get(name=f'{ifname} traffic', object_id=d.pk)
            points = self._read_metric(
                m, limit=10, order='-time', extra_fields=['tx_bytes']
            )
            self.assertEqual(len(points), 2)
            for field in ['rx_bytes', 'tx_bytes']:
                expected = iface['statistics'][field] - points[1][field]
                self.assertEqual(points[0][field], expected)
            m = self.metric_queryset.get(name=f'{ifname} wifi clients', object_id=d.pk)
            points = self._read_metric(m, limit=10, order='-time')
            self.assertEqual(len(points), len(iface['wireless']['clients']) * 2)

    def test_200_traffic_counter_reset(self):
        dd = self.create_test_data(no_resources=True)
        d = self.device_model.objects.first()
        data2 = self._data()
        # creation of resources metrics can be avoided here as it is not involved
        # this speeds up the test by reducing requests made
        del data2['resources']
        data2['interfaces'][0]['statistics']['rx_bytes'] = 50
        data2['interfaces'][0]['statistics']['tx_bytes'] = 20
        data2['interfaces'][1]['statistics']['rx_bytes'] = 80
        data2['interfaces'][1]['statistics']['tx_bytes'] = 120
        r = self._post_data(d.id, d.key, data2)
        self.assertEqual(r.status_code, 200)
        self.assertDataDict(dd.data, data2)
        # Add 1 for general metric and chart
        self.assertEqual(self.metric_queryset.count(), 4)
        self.assertEqual(self.chart_queryset.count(), 4)
        if_dict = {'wlan0': data2['interfaces'][0], 'wlan1': data2['interfaces'][1]}
        for ifname in ['wlan0', 'wlan1']:
            iface = if_dict[ifname]
            m = self.metric_queryset.get(name=f'{ifname} traffic', object_id=d.pk)
            points = self._read_metric(
                m, limit=10, order='-time', extra_fields=['tx_bytes']
            )
            self.assertEqual(len(points), 2)
            for field in ['rx_bytes', 'tx_bytes']:
                expected = iface['statistics'][field]
                self.assertEqual(points[0][field], expected)
            m = self.metric_queryset.get(name=f'{ifname} wifi clients', object_id=d.pk)
            points = self._read_metric(m, limit=10, order='-time')
            self.assertEqual(len(points), len(iface['wireless']['clients']) * 2)

    def test_device_with_location(self):
        self.create_test_data(no_resources=True)
        device = self.device_model.objects.first()
        location = self._create_location(
            organization=device.organization, type='indoor'
        )
        floorplan = self._create_floorplan(location=location)
        self._create_object_location(
            content_object=device, location=location, floorplan=floorplan
        )
        data2 = self._data()
        # creation of resources metrics can be avoided here as it is not involved
        # this speeds up the test by reducing requests made
        del data2['resources']
        additional_queries = 0 if self._is_timeseries_udp_writes else 1
        with self.assertNumQueries(21 + additional_queries):
            response = self._post_data(device.id, device.key, data2)
        # Ensure cache is working
        with self.assertNumQueries(13 + additional_queries):
            response = self._post_data(device.id, device.key, data2)
        self.assertEqual(response.status_code, 200)
        # Add 1 for general metric and chart
        self.assertEqual(self.metric_queryset.count(), 4)
        self.assertEqual(self.chart_queryset.count(), 4)
        for metric in self.metric_queryset.filter(object_id__isnull=False):
            points = self._read_metric(
                metric,
                limit=10,
                order='-time',
                extra_fields=['location_id', 'floorplan_id'],
            )
            for point in points:
                self.assertEqual(point['location_id'], str(location.id))
                self.assertEqual(point['floorplan_id'], str(floorplan.id))

    def test_200_multiple_measurements(self):
        dd = self._create_multiple_measurements(no_resources=True)
        # Add 1 for general metric and chart
        self.assertEqual(self.metric_queryset.count(), 4)
        self.assertEqual(self.chart_queryset.count(), 4)
        expected = {
            'wlan0': {'rx_bytes': 10000, 'tx_bytes': 6000},
            'wlan1': {'rx_bytes': 4587, 'tx_bytes': 2993},
        }
        # wlan0 traffic
        m = self.metric_queryset.get(name='wlan0 traffic', object_id=dd.pk)
        points = self._read_metric(
            m, limit=10, order='-time', extra_fields=['tx_bytes']
        )
        self.assertEqual(len(points), 4)
        expected = [700000000, 100000000, 399999676, 324]
        for i, point in enumerate(points):
            self.assertEqual(point['rx_bytes'], expected[i])
        expected = [300000000, 200000000, 99999855, 145]
        for i, point in enumerate(points):
            self.assertEqual(point['tx_bytes'], expected[i])
        c = m.chart_set.first()
        data = self._read_chart(c)
        # expected download wlan0
        self.assertEqual(data['traces'][0][1][-1], 1.2)
        # expected upload wlan0
        self.assertEqual(data['traces'][1][1][-1], 0.6)
        # wlan1 traffic
        m = self.metric_queryset.get(name='wlan1 traffic', object_id=dd.pk)
        points = self._read_metric(
            m, limit=10, order='-time', extra_fields=['tx_bytes']
        )
        self.assertEqual(len(points), 4)
        expected = [1000000000, 0, 1999997725, 2275]
        for i, point in enumerate(points):
            self.assertEqual(point['rx_bytes'], expected[i])
        expected = [500000000, 0, 999999174, 826]
        for i, point in enumerate(points):
            self.assertEqual(point['tx_bytes'], expected[i])
        c = m.chart_set.first()
        data = self._read_chart(c)
        # expected download wlan1
        self.assertEqual(data['traces'][0][1][-1], 3.0)
        # expected upload wlan1
        self.assertEqual(data['traces'][1][1][-1], 1.5)

    def test_200_no_date_supplied(self):
        o = self._create_org()
        d = self._create_device(organization=o)
        data = self._data()
        netjson = json.dumps(data)
        url = self._url(d.id, d.key)
        r = self.client.post(url, netjson, content_type='application/json')
        self.assertEqual(r.status_code, 200)

    def test_404_disabled_organization(self):
        org = self._create_org(is_active=False)
        device = self._create_device(organization=org)
        with self.assertNumQueries(2):
            response = self._post_data(device.id, device.key, self._data())
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.metric_queryset.count(), 0)
        self.assertEqual(self.chart_queryset.count(), 0)

    def test_device_activate_deactivate(self):
        # "self.create_test_data" creates a device and makes
        # a POST request to DeviceMetricView ensuring that
        # the device is cached.
        self.create_test_data(no_resources=True)
        device = self.device_model.objects.first()
        data = {'type': 'DeviceMonitoring'}
        with self.assertNumQueries(2):
            response = self._post_data(device.id, device.key, data)

        # Deactivating the device will invalidate the cache.
        # The view will only allow readonly requests (GET).
        device.deactivate()
        response = self.client.get(self._url(device.pk, device.key))
        self.assertEqual(response.status_code, 200)
        with self.assertNumQueries(1):
            response = self._post_data(device.id, device.key, data)
        self.assertEqual(response.status_code, 404)

        # Re-activating the device will allow POST requests again.
        device.activate()
        with self.assertNumQueries(4):
            response = self._post_data(device.id, device.key, data)
        self.assertEqual(response.status_code, 200)

    def test_garbage_wireless_clients(self):
        o = self._create_org()
        d = self._create_device(organization=o)
        garbage_interfaces = [
            {'name': 'garbage1', 'wireless': {'clients': {}}},
            {'name': 'garbage2', 'wireless': {'clients': [{'what?': 'mac missing'}]}},
            {'name': 'garbage3', 'wireless': {}},
        ]
        for garbage_interface in garbage_interfaces:
            interface = self._data()['interfaces'][0]
            interface.update(garbage_interface)
            r = self._post_data(
                d.id, d.key, {'type': 'DeviceMonitoring', 'interfaces': [interface]}
            )
            with self.subTest(garbage_interface):
                self.assertEqual(r.status_code, 400)

    @patch.object(monitoring_settings, 'AUTO_CHARTS', return_value=[])
    def test_auto_chart_disabled(self, *args):
        # Add 1 for general chart
        self.assertEqual(self.chart_queryset.count(), 0)
        o = self._create_org()
        d = self._create_device(organization=o)
        self._post_data(d.id, d.key, self._data())
        # Add 1 for general chart
        self.assertEqual(self.chart_queryset.count(), 0)

    def test_get_device_metrics_200(self):
        dd = self.create_test_data()
        d = self.device_model.objects.get(pk=dd.pk)
        with self.assertNumQueries(17):
            r = self.client.get(self._url(d.pk.hex, d.key))
        with self.assertNumQueries(16):
            r = self.client.get(self._url(d.pk.hex, d.key))
        self.assertEqual(r.status_code, 200)

        with self.subTest('Test device metrics 200 without the device key'):
            r1 = self.client.get(self._url(d.pk.hex))
            self.assertEqual(r1.status_code, 200)
            for key in self._RESPONSE_KEYS:
                self.assertIn(key, r.data.keys())

        with self.subTest('Test device information in the response'):
            self._assert_device_info(device=d, data=r.data)

        with self.subTest('Test device metrics in the response'):
            self._assert_device_metrics_info(data=r.data)

        with self.subTest('Test device charts in the response'):
            self.assertIn('x', r.data)
            charts = r.data['charts']
            for chart in charts:
                self.assertIn('traces', chart)
                self.assertIn('title', chart)
                self.assertIn('description', chart)
                self.assertIn('type', chart)
                self.assertIn('summary', chart)
                self.assertIsInstance(chart['summary'], dict)
                self.assertIn('summary_labels', chart)
                self.assertIsInstance(chart['summary_labels'], list)
                self.assertIn('unit', chart)
                self.assertIn('colors', chart)
                self.assertIn('colorscale', chart)
            # test charts order
            self.assertEqual(charts[0]['title'], 'WiFi clients: wlan0')
            self.assertEqual(charts[1]['title'], 'WiFi clients: wlan1')
            self.assertEqual(charts[2]['title'], 'Traffic: wlan0')
            self.assertEqual(charts[3]['title'], 'Traffic: wlan1')
            self.assertEqual(charts[4]['title'], 'Memory Usage')
            self.assertEqual(charts[5]['title'], 'CPU Load')
            self.assertEqual(charts[6]['title'], 'Disk Usage')

    def test_get_device_metrics_list_200(self):
        dd1 = self.create_test_data()
        url = reverse('monitoring:api_monitoring_device_list')
        d1 = self.device_model.objects.get(pk=dd1.pk)
        o2 = self._create_org(name='test org 2')
        d2 = self._create_device(
            name='test-device-2', mac_address='00:11:22:33:44:66', organization=o2
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['count'], 2)
        self.assertEqual(r.data['next'], None)
        self.assertEqual(r.data['previous'], None)
        results = r.data['results'][0].keys()
        _RESPONSE_KEYS = self._RESPONSE_KEYS.copy()
        _RESPONSE_KEYS.remove('x')
        _RESPONSE_KEYS.remove('charts')
        for key in _RESPONSE_KEYS:
            self.assertIn(key, results)
        self._assert_device_info(device=d1, data=r.data['results'][0])
        self._assert_device_info(device=d2, data=r.data['results'][1])
        self._assert_device_metrics_info(
            data=r.data['results'][0], detail=False, charts=False
        )

        with self.subTest('Test filtering using monitoring health status'):
            r = self.client.get(f'{url}?monitoring__status=ok')
            self.assertEqual(r.data['count'], 1)
            self._assert_device_info(device=d1, data=r.data['results'][0])
            self._assert_device_metrics_info(
                data=r.data['results'][0], detail=False, charts=False
            )
            # Update device (d2) health status to 'critical'
            d2.monitoring.update_status('critical')
            r = self.client.get(f'{url}?monitoring__status=critical')
            self.assertEqual(r.data['count'], 1)
            self._assert_device_info(device=d2, data=r.data['results'][0])
            self._assert_device_metrics_info(
                data=r.data['results'][0], detail=False, charts=False
            )

        with self.subTest('Test filtering using organization id'):
            r = self.client.get(f'{url}?organization={d1.organization.id}')
            self.assertEqual(r.data['count'], 1)
            self._assert_device_info(device=d1, data=r.data['results'][0])
            self._assert_device_metrics_info(
                data=r.data['results'][0], detail=False, charts=False
            )
            r = self.client.get(f'{url}?organization={d2.organization.id}')
            self.assertEqual(r.data['count'], 1)
            self._assert_device_info(device=d2, data=r.data['results'][0])
            self._assert_device_metrics_info(
                data=r.data['results'][0], detail=False, charts=False
            )

        with self.subTest('Test filtering using organization slug'):
            r = self.client.get(f'{url}?organization_slug={d1.organization.slug}')
            self.assertEqual(r.data['count'], 1)
            self._assert_device_info(device=d1, data=r.data['results'][0])
            self._assert_device_metrics_info(
                data=r.data['results'][0], detail=False, charts=False
            )
            r = self.client.get(f'{url}?organization_slug={d2.organization.slug}')
            self.assertEqual(r.data['count'], 1)
            self._assert_device_info(device=d2, data=r.data['results'][0])
            self._assert_device_metrics_info(
                data=r.data['results'][0], detail=False, charts=False
            )

    def test_get_device_metrics_histogram_ignore_x(self):
        o = self._create_org()
        d = self._create_device(organization=o)
        m = self._create_object_metric(content_object=d, name='applications')
        self._create_chart(metric=m, configuration='histogram')
        self._create_multiple_measurements(create=False, no_resources=True, count=2)
        r = self.client.get(self._url(d.pk.hex, d.key))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(len(r.data['x']) > 50)

    def test_get_device_metrics_1d(self):
        dd = self.create_test_data()
        d = self.device_model.objects.get(pk=dd.pk)
        r = self.client.get('{0}&time=1d'.format(self._url(d.pk, d.key)))
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.data['charts'], list)

    def test_get_device_metrics_404(self):
        r = self.client.get(self._url('WRONG', 'MADEUP'))
        self.assertEqual(r.status_code, 404)

    def test_get_device_metrics_401(self):
        d = self._create_device(organization=self._create_org())
        self.client.logout()
        # try to access the device metrics
        # ie. api view without authentication
        r = self.client.get(self._url(d.pk))
        self.assertEqual(r.status_code, 401)

    def test_get_device_list_metrics_401(self):
        self._create_device(organization=self._create_org())
        self.client.logout()
        # try to access the device metrics list
        # ie. api view without authentication
        url = reverse('monitoring:api_monitoring_device_list')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 401)

    def test_get_device_metrics_400_bad_time_range(self):
        d = self._create_device(organization=self._create_org())
        url = '{0}&time=3w'.format(self._url(d.pk, d.key))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 400)

    def test_get_device_metrics_csv(self):
        d = self._create_device(organization=self._create_org())
        self._create_multiple_measurements(create=False, count=2)
        m = self._create_object_metric(
            content_object=d, name='applications', configuration='get_top_fields'
        )
        self._create_chart(metric=m, configuration='histogram')
        m.write(None, extra_values={'http2': 90, 'ssh': 100, 'udp': 80, 'spdy': 70})
        r = self.client.get('{0}&csv=1'.format(self._url(d.pk, d.key)))
        self.assertEqual(r.get('Content-Disposition'), 'attachment; filename=data.csv')
        self.assertEqual(r.get('Content-Type'), 'text/csv')
        rows = r.content.decode('utf8').strip().split('\n')
        header = rows[0].strip().split(',')
        self.assertEqual(
            header,
            [
                'time',
                'wifi_clients - WiFi clients: wlan0',
                'wifi_clients - WiFi clients: wlan1',
                'download - Traffic: wlan0',
                'upload - Traffic: wlan0',
                'download - Traffic: wlan1',
                'upload - Traffic: wlan1',
                'memory_usage - Memory Usage',
                'CPU_load - CPU Load',
                'disk_usage - Disk Usage',
            ],
        )
        last_line_before_histogram = rows[-5].strip().split(',')
        self.assertEqual(
            last_line_before_histogram,
            [
                last_line_before_histogram[0],
                '1',
                '2',
                '0.4',
                '0.1',
                '2.0',
                '1.0',
                '9.73',
                '0.0',
                '8.27',
            ],
        )
        self.assertEqual(rows[-4].strip(), '')
        self.assertEqual(rows[-3].strip(), 'Histogram')
        self.assertEqual(rows[-2].strip().split(','), ['ssh', '100.0'])
        self.assertEqual(rows[-1].strip().split(','), ['http2', '90.0'])

    def test_histogram_csv_none_value(self):
        d = self._create_device(organization=self._create_org())
        m = self._create_object_metric(content_object=d, name='applications')
        mock = {
            'traces': [('http2', [100]), ('ssh', [None])],
            'x': ['2020-06-15 00:00'],
            'summary': {'http2': 100, 'ssh': None},
        }
        c = self._create_chart(metric=m, configuration='histogram')
        with patch(
            'openwisp_monitoring.monitoring.base.models.AbstractChart.read',
            return_value=mock,
        ):
            self.assertEqual(self._read_chart(c), mock)
            r = self.client.get('{0}&csv=1'.format(self._url(d.pk, d.key)))
        self.assertEqual(r.get('Content-Disposition'), 'attachment; filename=data.csv')
        self.assertEqual(r.get('Content-Type'), 'text/csv')
        rows = r.content.decode('utf8').strip().split('\n')
        self.assertEqual(rows[-2].strip().split(','), ['http2', '100'])
        self.assertEqual(rows[-1].strip().split(','), ['ssh', '0'])

    def test_get_device_metrics_empty(self):
        d = self._create_device(organization=self._create_org())
        m = self._create_object_metric(name='test_metric', content_object=d)
        c = Chart(metric=m, configuration='dummy')  # empty chart
        c.full_clean()
        c.save()
        # Add 1 for general chart
        self.assertEqual(self.chart_queryset.count(), 1)
        response = self.client.get(self._url(d.pk.hex, d.key))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['charts'], [])

    def test_get_device_metrics_400_bad_timezone(self):
        dd = self.create_test_data(no_resources=True)
        d = self.device_model.objects.get(pk=dd.pk)
        wrong_timezone_values = (
            'wrong',
            'America/Lima%27);%20DROP%20DATABASE%20test2;',
            'Europe/Cazzuoli',
        )
        for tz_value in wrong_timezone_values:
            url = '{0}&timezone={1}'.format(self._url(d.pk, d.key), tz_value)
            r = self.client.get(url)
            self.assertEqual(r.status_code, 400)
            self.assertIn('Unkown Time Zone', r.data)

    def test_device_metrics_received_signal(self):
        d = self._create_device(organization=self._create_org())
        dd = DeviceData(name='test-device', pk=d.pk)
        data = self._data()
        self._create_object_metric(name='ping', configuration='ping', content_object=d)
        time = start_time.strftime('%d-%m-%Y_%H:%M:%S.%f')
        with catch_signal(device_metrics_received) as handler:
            response = self._post_data(d.id, d.key, data, time=time)
        request = response.renderer_context['request']
        handler.assert_called_once_with(
            instance=dd,
            request=request,
            sender=DeviceData,
            signal=device_metrics_received,
            time=start_time,
            current=False,
        )

    @capture_any_output()
    def test_invalid_chart_config(self):
        # Tests if chart_config is invalid, then it is skipped and API does not fail
        d = self._create_device(organization=self._create_org())
        m = self._create_object_metric(name='test_metric', content_object=d)
        c = self._create_chart(metric=m, test_data=None)
        c.configuration = 'invalid'
        c.save()
        response = self.client.get(self._url(d.pk.hex, d.key))
        self.assertEqual(response.status_code, 200)

    def test_available_memory(self):
        o = self._create_org()
        d = self._create_device(organization=o)
        data = self._data()
        data['resources']['memory']['free'] = 224497664
        with self.subTest('Test without available memory'):
            del data['resources']['memory']['available']
            r = self._post_data(d.id, d.key, data)
            m = self.metric_queryset.get(key='memory')
            metric_data = self._read_metric(m, order='-time', extra_fields='*')[0]
            self.assertEqual(metric_data['percent_used'], 9.729419481797308)
            self.assertIsNone(metric_data.get('available_memory'))
            self.assertEqual(r.status_code, 200)
        with self.subTest('Test when available memory is less than free memory'):
            data['resources']['memory']['available'] = 2232664
            r = self._post_data(d.id, d.key, data)
            metric_data = self._read_metric(m, order='-time', extra_fields='*')[0]
            self.assertEqual(metric_data['percent_used'], 9.729419481797308)
            self.assertEqual(metric_data['available_memory'], 2232664)
            self.assertEqual(r.status_code, 200)
        with self.subTest('Test when available memory is greater than free memory'):
            data['resources']['memory']['available'] = 225567664
            r = self._post_data(d.id, d.key, data)
            m = self.metric_queryset.get(key='memory')
            metric_data = self._read_metric(m, order='-time', extra_fields='*')[0]
            self.assertEqual(metric_data['percent_used'], 9.301032356920302)
            self.assertEqual(metric_data['available_memory'], 225567664)
            self.assertEqual(r.status_code, 200)

    def test_get_device_status_200(self):
        dd = self.create_test_data(no_resources=True)
        d = self.device_model.objects.get(pk=dd.pk)
        url = self._url(d.pk.hex, d.key)
        # status not requested
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('status', r.data)
        # status requested
        r = self.client.get(f'{url}&status=1')
        self.assertEqual(r.status_code, 200)
        self.assertIn('data', r.data)
        self.assertIsInstance(r.data['data'], dict)
        self.assertEqual(dd.data, r.data['data'])

    def test_garbage_interface_properties(self):
        o = self._create_org()
        d = self._create_device(organization=o)
        garbage_interfaces = [
            {'type': 1},
            {'uptime': 'string'},
            {'up': 'up'},
            {'mac': 1},
            {'mtu': 'string'},
            {'txqueuelen': 'string'},
            {'speed': 0},
            {'multicast': 1},
            {'type': 'bridge', 'bridge_members': [1, 2]},
            {'stp': 1},
        ]
        number = 1
        for garbage_interface in garbage_interfaces:
            interface = self._data()['interfaces'][0]
            interface.update(garbage_interface)
            interface['name'] = f'garbage{number}'
            r = self._post_data(
                d.id, d.key, {'type': 'DeviceMonitoring', 'interfaces': [interface]}
            )
            number += 1
            with self.subTest(garbage_interface):
                self.assertEqual(r.status_code, 400)

    def test_mobile_properties(self):
        org = self._create_org()
        device = self._create_device(organization=org)
        data = {
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
        }
        response = self._post_data(device.id, device.key, data)
        self.assertEqual(response.status_code, 200)
        mobile_data = DeviceData(pk=device.pk).data['interfaces'][0]['mobile']
        with self.subTest('check mobile interface static properties'):
            self.assertEqual(mobile_data['connection_status'], 'connected')
            self.assertEqual(mobile_data['imei'], '300000001234567')
            self.assertEqual(mobile_data['model'], 'MC7430')
            self.assertEqual(mobile_data['operator_code'], '50502')
            self.assertEqual(mobile_data['operator_name'], 'YES OPTUS')
            self.assertEqual(mobile_data['power_status'], 'on')
        with self.subTest('ensure signal data is converted to float'):
            # ensure numbers are stored as floats,
            # lua cannot be forced to send floats so we need to force it
            self.assertIsInstance(mobile_data['signal']['lte']['rsrp'], float)
            self.assertIsInstance(mobile_data['signal']['lte']['rsrq'], float)
            self.assertIsInstance(mobile_data['signal']['lte']['rssi'], float)
            self.assertIsInstance(mobile_data['signal']['lte']['snr'], float)
            self.assertDictEqual(
                mobile_data['signal'],
                {'lte': {'rsrp': -75.00, 'rsrq': -8.00, 'rssi': -51.00, 'snr': 13.00}},
            )

    def test_empty_mobile_signal_data(self):
        org = self._create_org()
        device = self._create_device(organization=org)
        data = {
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
                        'signal': {'threshold': {'rssi': '0.0'}},
                    },
                }
            ],
        }
        response = self._post_data(device.id, device.key, data)
        self.assertEqual(response.status_code, 200)
        mobile_data = DeviceData(pk=device.pk).data['interfaces'][0]['mobile']
        with self.subTest('check mobile interface static properties'):
            self.assertEqual(mobile_data['imei'], '300000001234567')
            self.assertEqual(mobile_data['model'], 'MC7430')
            self.assertIn('signal', mobile_data)
            self.assertIn('threshold', mobile_data['signal'])

    def test_garbage_mobile_properties(self):
        o = self._create_org()
        d = self._create_device(organization=o)
        interface = {
            'name': 'mobile',
            'mac': '00:00:00:00:00:00',
            'mtu': 1900,
            'multicast': True,
            'txqueuelen': 1000,
            'type': 'modem-manager',
            'up': True,
        }
        garbage_data = [
            {'connection_status': 'connected'},
            {'imei': '300000001234567'},
            {
                'connection_status': 'connected',
                'imei': '300000001234567',
                'manufacturer': 'Sierra Wireless, Incorporated',
                'model': 'MC7430',
                'operator_code': '50502',
                'operator_name': 'YES OPTUS',
                'power_status': 'on',
                'signal': {'lte': {'rsrp': -75}},
            },
            {
                'connection_status': 'connected',
                'imei': '300000001234567',
                'manufacturer': 'Sierra Wireless, Incorporated',
                'model': 'MC7430',
                'operator_code': '50502',
                'operator_name': 'YES OPTUS',
                'power_status': 'on',
                'signal': {
                    'lte': {'rsrp': '-75', 'rsrq': '-8', 'rssi': '-51', 'snr': '13'}
                },
            },
        ]
        number = 0
        for mobile_data in garbage_data:
            interface_data = interface.copy()
            interface_data['mobile'] = mobile_data
            interface_data['name'] += str(number)
            r = self._post_data(
                d.id,
                d.key,
                {'type': 'DeviceMonitoring', 'interfaces': [interface_data]},
            )
            number += 1
            with self.subTest(interface_data['name']):
                self.assertEqual(r.status_code, 400)

    def test_mobile_charts(self):
        org = self._create_org()
        device = self._create_device(organization=org)
        charts_count = self.chart_queryset.count()
        data = {
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
                            'lte': {'rsrp': -75, 'rsrq': -8, 'rssi': -51, 'snr': 13},
                        },
                    },
                }
            ],
        }
        self._post_data(device.id, device.key, data)
        data['interfaces'][0]['mobile']['signal'].update(
            {'umts': {'ecio': 2, 'rscp': -14, 'rssi': -80}}
        )
        self._post_data(device.id, device.key, data)
        response = self.client.get(self._url(device.pk.hex, device.key))
        self.assertEqual(response.status_code, 200)
        charts = response.data['charts']
        self.assertEqual(charts[0]['summary']['signal_strength'], -51.0)
        self.assertEqual(charts[0]['summary']['signal_power'], -75.0)
        self.assertEqual(charts[1]['summary']['signal_quality'], -8.0)
        self.assertEqual(charts[1]['summary']['signal_to_noise_ratio'], 13.0)
        self.assertEqual(charts[2]['summary']['access_tech'], 4.0)
        # ensure correct color-coding
        self.assertEqual(
            charts[2]['colorscale']['map'],
            [
                [5, '#377873', '5g'],
                [4, '#67c368', 'lte'],
                [3, '#efdd50', 'umts'],
                [2, '#df7514', 'evdo'],
                [1, '#dd5817', 'cdma1x'],
                [0, '#b42a0c', 'gsm'],
            ],
        )
        self.assertEqual(self.chart_queryset.count(), charts_count + 3)

    def test_5g_charts(self):
        org = self._create_org()
        device = self._create_device(organization=org)
        data = {
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
                            'lte': {'rsrp': -75, 'rsrq': -8, 'rssi': -51, 'snr': 13},
                            '5g': {'rsrp': -70, 'rsrq': -7, 'snr': 12},
                        },
                    },
                }
            ],
        }
        response = self._post_data(device.id, device.key, data)
        self.assertEqual(response.status_code, 200)
        response = self.client.get(self._url(device.pk.hex, device.key))
        self.assertEqual(response.status_code, 200)
        charts = response.data['charts']
        self.assertEqual(charts[0]['summary']['signal_power'], -70.0)
        self.assertEqual(charts[0]['summary']['signal_strength'], None)
        self.assertEqual(charts[1]['summary']['signal_quality'], -7.0)
        self.assertEqual(charts[1]['summary']['signal_to_noise_ratio'], 12.0)
        self.assertEqual(charts[2]['summary']['access_tech'], 5)

    def test_umts_rscp_missing(self):
        org = self._create_org()
        device = self._create_device(organization=org)
        data = {
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
                        'signal': {'umts': {'ecio': -5, 'rssi': -69}},
                    },
                }
            ],
        }
        response = self._post_data(device.id, device.key, data)
        self.assertEqual(response.status_code, 200)
        response = self.client.get(self._url(device.pk.hex, device.key))
        self.assertEqual(response.status_code, 200)
        charts = response.data['charts']
        self.assertEqual(len(charts), 3)
        self.assertEqual(charts[0]['summary']['signal_strength'], -69.0)
        self.assertEqual(charts[0]['summary']['signal_power'], None)
        self.assertEqual(charts[1]['summary']['signal_quality'], None)
        self.assertEqual(charts[1]['summary']['signal_to_noise_ratio'], -5.0)
        self.assertEqual(charts[2]['summary']['access_tech'], 3.0)

    def test_umts_rssi_missing(self):
        org = self._create_org()
        device = self._create_device(organization=org)
        data = {
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
                        'signal': {'umts': {'ecio': -3.50, 'rscp': -96.00}},
                    },
                }
            ],
        }
        response = self._post_data(device.id, device.key, data)
        self.assertEqual(response.status_code, 200)
        response = self.client.get(self._url(device.pk.hex, device.key))
        self.assertEqual(response.status_code, 200)
        charts = response.data['charts']
        self.assertEqual(len(charts), 3)
        self.assertEqual(charts[0]['summary']['signal_strength'], None)
        self.assertEqual(charts[0]['summary']['signal_power'], -96.00)
        self.assertEqual(charts[1]['summary']['signal_quality'], None)
        self.assertEqual(charts[1]['summary']['signal_to_noise_ratio'], -4)
        self.assertEqual(charts[2]['summary']['access_tech'], 3.0)

    def test_cdma_charts(self):
        org = self._create_org()
        device = self._create_device(organization=org)
        data = {
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
                        'signal': {'cdma1x': {'ecio': -5, 'rssi': -69}},
                    },
                }
            ],
        }
        response = self._post_data(device.id, device.key, data)
        self.assertEqual(response.status_code, 200)
        response = self.client.get(self._url(device.pk.hex, device.key))
        self.assertEqual(response.status_code, 200)
        charts = response.data['charts']
        self.assertEqual(len(charts), 3)
        self.assertEqual(charts[0]['summary']['signal_strength'], -69.0)
        self.assertEqual(charts[0]['summary']['signal_power'], None)
        self.assertEqual(charts[1]['summary']['signal_quality'], None)
        self.assertEqual(charts[1]['summary']['signal_to_noise_ratio'], -5.0)
        self.assertEqual(charts[2]['summary']['access_tech'], 1.0)

    def test_evdo_charts(self):
        org = self._create_org()
        device = self._create_device(organization=org)
        data = {
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
                            'evdo': {'ecio': -5, 'rssi': -69, 'io': -70, 'sinr': -11},
                        },
                    },
                }
            ],
        }
        response = self._post_data(device.id, device.key, data)
        self.assertEqual(response.status_code, 200)
        response = self.client.get(self._url(device.pk.hex, device.key))
        self.assertEqual(response.status_code, 200)
        charts = response.data['charts']
        self.assertEqual(len(charts), 3)
        self.assertEqual(charts[0]['summary']['signal_strength'], -69.0)
        self.assertEqual(charts[0]['summary']['signal_power'], None)
        self.assertEqual(charts[1]['summary']['signal_quality'], None)
        self.assertEqual(charts[1]['summary']['signal_to_noise_ratio'], -11.0)
        self.assertEqual(charts[2]['summary']['access_tech'], 2.0)

    def test_gsm_charts(self):
        org = self._create_org()
        device = self._create_device(organization=org)
        data = {
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
                        'signal': {'gsm': {'rssi': -70}},
                    },
                }
            ],
        }
        response = self._post_data(device.id, device.key, data)
        self.assertEqual(response.status_code, 200)
        response = self.client.get(self._url(device.pk.hex, device.key))
        self.assertEqual(response.status_code, 200)
        charts = response.data['charts']
        self.assertEqual(len(charts), 2)
        self.assertEqual(charts[0]['summary']['signal_power'], None)
        self.assertEqual(charts[0]['summary']['signal_strength'], -70.0)

    def test_mobile_signal_missing(self):
        org = self._create_org()
        device = self._create_device(organization=org)
        data = {
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
                        'imei': '865847055230161',
                        'manufacturer': 'QUALCOMM INCORPORATED',
                        'model': 'QUECTEL Mobile Broadband Module',
                        'operator_code': '22250',
                        'operator_name': 'Iliad',
                        'power_status': 'on',
                        'signal': {},
                    },
                }
            ],
        }
        self._post_data(device.id, device.key, data)
        response = self.client.get(self._url(device.pk.hex, device.key))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['charts'], [])
        dd = DeviceData(name=device.name, pk=device.pk)
        self.assertEqual(
            dd.data['interfaces'][0]['mobile'], data['interfaces'][0]['mobile']
        )

        with self.subTest('signal key not present at all'):
            del data['interfaces'][0]['mobile']['signal']
            response = self._post_data(device.id, device.key, data)
            self.assertEqual(response.status_code, 200)

    def test_pre_metric_write_signal(self):
        d = self._create_device(organization=self._create_org())
        data = {'type': 'DeviceMonitoring', 'resources': {'cpus': 1, 'load': [0, 0, 0]}}
        self._create_object_metric(
            name='CPU usage', configuration='cpu', object_id=d.id
        )
        values = {'cpu_usage': 0.0, 'load_1': 0.0, 'load_5': 0.0, 'load_15': 0.0}
        time = start_time.strftime('%d-%m-%Y_%H:%M:%S.%f')
        with catch_signal(pre_metric_write) as handler:
            self._post_data(d.id, d.key, data, time=time)
        signal_calls = handler.call_args_list
        # assert signal is called once
        self.assertEqual(len(signal_calls), 1)
        signal_arguments = signal_calls[0][1]
        # remove metric from signal arguments
        del signal_arguments['metric']
        expected_arguments = dict(
            signal=pre_metric_write,
            sender=Metric,
            values=values,
            time=start_time,
            current=False,
        )
        self.assertEqual(signal_calls[0][1], expected_arguments)

    def test_post_metric_write_signal(self):
        d = self._create_device(organization=self._create_org())
        data = {'type': 'DeviceMonitoring', 'resources': {'cpus': 1, 'load': [0, 0, 0]}}
        self._create_object_metric(
            name='CPU usage', configuration='cpu', object_id=d.id
        )
        values = {'cpu_usage': 0.0, 'load_1': 0.0, 'load_5': 0.0, 'load_15': 0.0}
        time = start_time.strftime('%d-%m-%Y_%H:%M:%S.%f')
        with catch_signal(post_metric_write) as handler:
            self._post_data(d.id, d.key, data, time=time)
        signal_calls = handler.call_args_list
        # assert signal is called once
        self.assertEqual(len(signal_calls), 1)
        signal_arguments = signal_calls[0][1]
        # remove metric from signal arguments
        del signal_arguments['metric']
        expected_arguments = dict(
            signal=post_metric_write,
            sender=Metric,
            values=values,
            time=start_time.isoformat(),
            current=False,
        )
        self.assertEqual(signal_calls[0][1], expected_arguments)

    def test_device_custom_date_metrics(self):
        now = datetime.now()
        dd = self.create_test_data()
        d = self.device_model.objects.get(pk=dd.pk)

        def _assert_chart_group(url, status_code, expected):
            response = self.client.get(url)
            chart_group = Chart._get_group_map(expected[0]).items()
            self.assertEqual(response.status_code, status_code)
            self.assertIn(expected, chart_group)

        with self.subTest('Test custom grouping between 1 to 2 days'):
            custom_date_query = '&start=2022-10-02%2000:00:00&end=2022-10-04%2023:59:59'
            url = f'{self._url(d.pk, d.key)}{custom_date_query}'
            _assert_chart_group(url, 200, ('2d', '10m'))

        with self.subTest('Test custom grouping between 3 to 6 days'):
            custom_date_query = '&start=2022-10-02%2000:00:00&end=2022-10-06%2023:59:59'
            url = f'{self._url(d.pk, d.key)}{custom_date_query}'
            _assert_chart_group(url, 200, ('4d', '25m'))

        with self.subTest('Test custom grouping between 8 to 27 days'):
            custom_date_query = '&start=2022-09-29%2000:00:00&end=2022-10-11%2015:50:56'
            url = f'{self._url(d.pk, d.key)}{custom_date_query}'
            _assert_chart_group(url, 200, ('12d', '2h'))

        with self.subTest('Test custom grouping between 28 to 364 days'):
            custom_date_query = '&start=2022-07-04%2000:00:00&end=2022-10-11%2015:50:56'
            url = f'{self._url(d.pk, d.key)}{custom_date_query}'
            _assert_chart_group(url, 200, ('99d', '1d'))

        with self.subTest('Test invalid custom dates'):
            invalid_custom_dates = (
                '&start=2022-07-04&end=2022-10-11',
                '&start=September&end=October',
                '&start=2022-07-04&end=10-11-2022%2015:50:56',
                '&start=09-08-2022%2000:00:00&end=10-11-2022%2016:39:29',
            )
            for invalid_date in invalid_custom_dates:
                url = f'{self._url(d.pk, d.key)}{invalid_date}'
                r = self.client.get(url)
                self.assertEqual(r.status_code, 400)
                self.assertIn(
                    'Incorrect custom date format, should be YYYY-MM-DD H:M:S', r.data
                )
        with self.subTest(
            'Test device metrics when start date is greater than end date'
        ):
            start_greater_than_end = (
                '&start=2022-09-23%2000:00:00&end=2022-09-13%2023:59:59'
            )
            url = f'{self._url(d.pk, d.key)}{start_greater_than_end}'
            r = self.client.get(url)
            self.assertEqual(r.status_code, 400)
            self.assertIn(
                'start_date cannot be greater than end_date',
                r.data,
            )
        with self.subTest(
            'Test device metrics when start date is greater than today date'
        ):
            start_greater = (now + timedelta(days=5)).strftime('%Y-%m-%d')
            end_greater = (now + timedelta(days=9)).strftime('%Y-%m-%d')
            start_greater_than_now = (
                f'&start={start_greater}%2000:00:00&end={end_greater}%2023:59:59'
            )
            url = f'{self._url(d.pk, d.key)}{start_greater_than_now}'
            r = self.client.get(url)
            self.assertEqual(r.status_code, 400)
            self.assertIn(
                "start_date cannot be greater than today's date",
                r.data,
            )
        with self.subTest(
            'Test device metrics when end date is greater than today date'
        ):
            start_lesser = (now - timedelta(days=2)).strftime('%Y-%m-%d')
            end_greater = (now + timedelta(days=5)).strftime('%Y-%m-%d')
            end_greater_than_now = (
                f'&start={start_lesser}%2000:00:00&end={end_greater}%2023:59:59'
            )
            url = f'{self._url(d.pk, d.key)}{end_greater_than_now}'
            r = self.client.get(url)
            self.assertEqual(r.status_code, 400)
            self.assertIn(
                "end_date cannot be greater than today's date",
                r.data,
            )

        with self.subTest(
            'Test device metrics when date range is greater than 365 days'
        ):
            greater_than_365_days = (
                '&start=2021-11-11%2000:00:00&end=2022-11-12%2023:59:59'
            )
            url = f'{self._url(d.pk, d.key)}{greater_than_365_days}'
            r = self.client.get(url)
            self.assertEqual(r.status_code, 400)
            self.assertIn(
                "The date range shouldn't be greater than 365 days",
                r.data,
            )

        with self.subTest('Test device metrics csv export with custom dates'):
            end_date = now.strftime('%Y-%m-%d')
            start_date = (now - timedelta(days=2)).strftime('%Y-%m-%d')
            self._create_multiple_measurements(create=False, count=2)
            m = self._create_object_metric(
                content_object=d, name='applications', configuration='get_top_fields'
            )
            self._create_chart(metric=m, configuration='histogram')
            m.write(None, extra_values={'http2': 90, 'ssh': 100, 'udp': 80, 'spdy': 70})
            custom_date_query = (
                f'&start={start_date}%2000:00:00&end={end_date}%2000:00:00'
            )
            url = f'{self._url(d.pk, d.key)}{custom_date_query}&csv=1'
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response.get('Content-Disposition'), 'attachment; filename=data.csv'
            )
            self.assertEqual(response.get('Content-Type'), 'text/csv')
            rows = response.content.decode('utf8').strip().split('\n')
            self.assertEqual(rows[-3].strip(), 'Histogram')
            self.assertEqual(rows[-2].strip().split(','), ['ssh', '100.0'])
            self.assertEqual(rows[-1].strip().split(','), ['http2', '90.0'])

    def test_missing_rx_bytes(self):
        """
        Regression test for:
        https://github.com/openwisp/openwisp-monitoring/issues/595
        """
        data = self._data()
        del data['interfaces'][0]['statistics']['rx_bytes']
        dd = self.create_test_data(no_resources=True, data=data, assertions=False)
        qs = Metric.objects.filter(
            object_id=dd.pk, key='traffic', main_tags={'ifname': 'wlan0'}
        )
        self.assertEqual(qs.count(), 1)
        m = qs.first()
        points = self._read_metric(m, limit=1, extra_fields=['tx_bytes'])
        self.assertEqual(points[0].get('tx_bytes'), 145)
        self.assertEqual(points[0].get('rx_bytes'), 0)

    def test_missing_tx_bytes(self):
        data = self._data()
        del data['interfaces'][0]['statistics']['tx_bytes']
        dd = self.create_test_data(no_resources=True, data=data, assertions=False)
        qs = Metric.objects.filter(
            object_id=dd.pk, key='traffic', main_tags={'ifname': 'wlan0'}
        )
        self.assertEqual(qs.count(), 1)
        m = qs.first()
        points = self._read_metric(m, limit=1, extra_fields=['tx_bytes'])
        self.assertEqual(points[0].get('rx_bytes'), 324)
        self.assertEqual(points[0].get('tx_bytes'), 0)


class TestGeoApi(TestGeoMixin, AuthenticationMixin, DeviceMonitoringTestCase):
    location_model = Location
    object_location_model = DeviceLocation
    object_model = Device
    floorplan_model = FloorPlan

    def _login_admin(self):
        User = get_user_model()
        admin = User.objects.create_superuser('admin', 'admin', 'test@test.com')
        self.client.force_login(admin)

    def test_api_location_geojson(self):
        device_location = self._create_object_location()
        device_location.device.monitoring.update_status('ok')
        self._login_admin()
        url = reverse('monitoring:api_location_geojson')
        response = self.client.get(url)
        data = response.data
        self.assertEqual(data['count'], 1)
        self.assertEqual(len(data['features']), 1)
        self.assertEqual(data['features'][0]['properties']['device_count'], 1)
        self.assertEqual(data['features'][0]['properties']['ok_count'], 1)
        self.assertEqual(data['features'][0]['properties']['problem_count'], 0)
        self.assertEqual(data['features'][0]['properties']['critical_count'], 0)
        self.assertEqual(data['features'][0]['properties']['unknown_count'], 0)

    def test_api_location_device_list(self):
        device_location = self._create_object_location()
        device_location.device.monitoring.update_status('ok')
        location = device_location.location
        self._login_admin()
        url = reverse('monitoring:api_location_device_list', args=[location.pk])
        response = self.client.get(url)
        data = response.data
        self.assertEqual(data['count'], 1)
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['id'], str(device_location.device.id))
        self.assertIn('monitoring', data['results'][0])
        self.assertIsInstance(data['results'][0]['monitoring'], dict)
        self.assertDictEqual(
            data['results'][0]['monitoring'], {'status': 'ok', 'status_label': 'ok'}
        )

    def test_api_monitoring_nearby_device_list(self):
        admin = self._create_admin()
        self.client.force_login(admin)
        org1 = self._get_org()
        org2 = self._create_org(name='org2', slug='org2')
        device_without_location = self._create_device(organization=org1)
        org1_device1 = self._create_device(
            mac_address='11:22:33:44:55:66',
            name='device1',
            organization=org1,
            model='TP-Link Archer C20',
        )
        org1_device2 = self._create_device(
            mac_address='11:22:33:44:55:67',
            name='device2',
            organization=org1,
            model='TP-Link Archer C50',
        )
        org2_device1 = self._create_device(
            mac_address='11:22:33:44:55:68',
            name='device3',
            organization=org2,
            model='TP-Link Archer C60',
        )
        org2_device1.monitoring.status = 'ok'
        org2_device1.monitoring.save()

        self._create_object_location(
            content_object=org1_device1,
            location=Location.objects.create(
                organization=org1,
                name='location1',
                address='Uttrakhand',
                geometry='SRID=4326;POINT (79.0676 30.7333)',
                type='outdoor',
            ),
        )
        self._create_object_location(
            content_object=org1_device2,
            location=Location.objects.create(
                organization=org1,
                name='location2',
                address='Sunnyvale',
                geometry='SRID=4326;POINT (-122.03749 37.37187)',
                type='outdoor',
            ),
        )
        self._create_object_location(
            content_object=org2_device1,
            location=Location.objects.create(
                organization=org2,
                name='location3',
                address='Brussels',
                geometry='SRID=4326;POINT (4.406264339 50.89806471)',
                type='outdoor',
            ),
        )
        with self.subTest('Test DeviceLocation does not exist'):
            response = self.client.get(
                reverse(
                    'monitoring:api_monitoring_nearby_device_list',
                    args=[device_without_location.id],
                )
            )
            self.assertEqual(response.status_code, 404)

        path = reverse(
            'monitoring:api_monitoring_nearby_device_list', args=[org1_device1.id]
        )
        with self.subTest('Test device list'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['count'], 2)
            self.assertIn('distance', response.data['results'][0])
            self.assertIsInstance(response.data['results'][0]['distance'], float)
            self.assertIn('monitoring_status', response.data['results'][0])
            self.assertIn('monitoring_data', response.data['results'][0])

        with self.subTest('Test filtering by model'):
            response = self.client.get(path, data={'model': 'TP-Link Archer C50'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['count'], 1)
            self.assertEqual(response.data['results'][0]['model'], 'TP-Link Archer C50')
            # Test filtering with multiple models
            response = self.client.get(
                path, data={'model': 'TP-Link Archer C50|TP-Link Archer C60'}
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['count'], 2)

        with self.subTest('Test filtering by monitoring status'):
            response = self.client.get(path, data={'monitoring__status': 'ok'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['count'], 1)
            self.assertEqual(response.data['results'][0]['monitoring_status'], 'ok')

        with self.subTest('Test filtering by distance'):
            response = self.client.get(path, data={'distance__lte': '6373400'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['count'], 1)
            self.assertEqual(response.data['results'][0]['distance'], 6373400)

        with self.subTest('Test pagination'):
            response = self.client.get(path, data={'page_size': '1'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['count'], 2)
            self.assertEqual(len(response.data['results']), 1)
            self.assertEqual(response.data['previous'], None)
            self.assertNotEqual(response.data['next'], None)

        user = self._create_org_user(is_admin=True, organization=org1).user
        user.groups.add(Group.objects.get(name='Administrator'))
        self.client.force_login(user)
        with self.subTest('Test multi-tenancy'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['count'], 1)
            self.assertEqual(response.data['results'][0]['id'], str(org1_device2.id))
            self.assertNotEqual(response.data['results'][0]['id'], str(org2_device1.id))

        self.client.logout()
        with self.subTest('Test device key authentication'):
            response = self.client.get(path, data={'key': org1_device1.key})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['count'], 2)
            # Test with inccorect device key
            response = self.client.get(path, data={'key': 'incorrect'})
            self.assertEqual(response.status_code, 404)

    @capture_any_output()
    def test_bearer_authentication(self):
        user = self._create_admin()
        token = Token.objects.create(user=user).key
        device_location = self._create_object_location()
        location = device_location.location

        with self.subTest('Test MonitoringGeoJsonLocationList'):
            response = self.client.get(
                reverse('monitoring:api_location_geojson'),
                content_type='application/json',
                HTTP_AUTHORIZATION=f'Bearer {token}',
            )
            self.assertEqual(response.status_code, 200)

        with self.subTest('Test GeoJsonLocationListView'):
            response = self.client.get(
                reverse('monitoring:api_location_device_list', args=[location.id]),
                content_type='application/json',
                HTTP_AUTHORIZATION=f'Bearer {token}',
            )
            self.assertEqual(response.status_code, 200)

        with self.subTest('Test MonitoringNearbyDeviceList'):
            response = self.client.get(
                reverse(
                    'monitoring:api_monitoring_nearby_device_list',
                    args=[device_location.content_object_id],
                ),
                content_type='application/json',
                HTTP_AUTHORIZATION=f'Bearer {token}',
            )
            self.assertEqual(response.status_code, 200)


class TestWifiSessionApi(
    AuthenticationMixin,
    TestMultitenantAdminMixin,
    TestWifiClientSessionMixin,
    CreateDeviceGroupMixin,
    DeviceMonitoringTestCase,
):
    def _login_admin(self):
        self._login()

    def _serialize_wifi_session(self, wifi_session, many=False, list_single=False):
        if many:
            serializer = WifiSessionSerializer(wifi_session, many=many)
            return serializer.data
        if list_single:
            serializer = WifiSessionSerializer(wifi_session)
            return serializer.data
        serializer = WifiSessionSerializer()
        return dict(serializer.to_representation(wifi_session))

    def _create_wifi_session_multi_env(self):
        org1 = self._get_org()
        dg1 = self._create_device_group(organization=org1)
        d1 = self._create_device(
            mac_address='00:11:22:33:44:66', group=dg1, organization=org1
        )
        ws1 = self._create_wifi_session(device=d1)
        ws1.wifi_client
        org2 = self._create_org(name='test-org-2')
        dg2 = self._create_device_group(organization=org2)
        d2 = self._create_device(
            mac_address='00:11:22:33:44:77', group=dg2, organization=org2
        )
        wc2 = self._create_wifi_client(mac_address='22:33:44:55:66:88')
        ws2 = self._create_wifi_session(device=d2, wifi_client=wc2)
        return org1, org2, d1, d2, dg1, dg2, ws1, ws2

    def _assert_wifi_session_list_filters(self, query_num, ws, filter_params={}):
        url = reverse('monitoring:api_wifi_session_list')
        with self.assertNumQueries(query_num):
            response = self.client.get(url, filter_params)
        self.assertEqual(response.status_code, 200)
        serializer_dict = self._serialize_wifi_session(ws, list_single=True)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0], serializer_dict)

    def test_wifi_session_list_unauthorized(self):
        device = self._create_device()
        wifi_session = self._create_wifi_session(device=device)
        with self.assertNumQueries(0):
            response = self.client.get(
                reverse('monitoring:api_wifi_session_detail', args=[wifi_session.id])
            )
        self.assertEqual(response.status_code, 401)
        response = self.client.get(reverse('monitoring:api_wifi_session_list'))
        self.assertEqual(response.status_code, 401)

    def test_wifi_session_detail_unauthorized(self):
        wifi_session = self._create_wifi_session()
        url = reverse('monitoring:api_wifi_session_detail', args=[wifi_session.id])
        with self.assertNumQueries(0):
            response = self.client.get(url)
        self.assertEqual(response.status_code, 401)

    def test_wifi_session_detail_404(self):
        wifi_session_id = uuid4()
        self._login_admin()
        url = reverse('monitoring:api_wifi_session_detail', args=[wifi_session_id])
        with self.assertNumQueries(2):
            response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_wifi_session_detail_get(self):
        device = self._create_device()
        wifi_session = self._create_wifi_session(device=device)
        wifi_session.wifi_client
        self._login_admin()
        url = reverse('monitoring:api_wifi_session_detail', args=[wifi_session.id])
        with self.assertNumQueries(2):
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        serializer_dict = self._serialize_wifi_session(wifi_session)
        self.assertEqual(response.data, serializer_dict)

    def test_wifisession_list_get(self):
        self._create_wifi_session_multi_env()
        self._login_admin()
        url = reverse('monitoring:api_wifi_session_list')
        with self.assertNumQueries(3):
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        wifi_session_qs = WifiSession.objects.order_by('-start_time')
        serializer_list = self._serialize_wifi_session(wifi_session_qs, many=True)
        self.assertEqual(response.data['results'], serializer_list)

    def test_wifisession_list_filters(self):
        org1, org2, d1, d2, dg1, dg2, ws1, ws2 = self._create_wifi_session_multi_env()
        self._login_admin()

        with self.subTest('Test filtering using organization id'):
            self._assert_wifi_session_list_filters(
                4, ws1, {'device__organization': org1.id}
            )
            self._assert_wifi_session_list_filters(
                4, ws2, {'device__organization': org2.id}
            )

        with self.subTest('Test filtering using device id'):
            self._assert_wifi_session_list_filters(4, ws1, {'device': d1.id})
            self._assert_wifi_session_list_filters(4, ws2, {'device': d2.id})

        with self.subTest('Test filtering using device group id'):
            self._assert_wifi_session_list_filters(4, ws1, {'device__group': dg1.id})
            self._assert_wifi_session_list_filters(4, ws2, {'device__group': dg2.id})

        with self.subTest('Test filtering using start time'):
            filter_time = ws2.start_time
            url = reverse('monitoring:api_wifi_session_list')
            wifi_session_qs = WifiSession.objects.order_by('-start_time')
            response = self.client.get(url, {'start_time': filter_time})
            self.assertEqual(response.data['count'], 1)
            # Make sure the correct WiFi session is returned in the response
            serializer_dict = self._serialize_wifi_session(ws2, list_single=True)
            self.assertEqual(response.data['results'][0], serializer_dict)
            response = self.client.get(url, {'start_time__gt': filter_time})
            self.assertEqual(response.data['count'], 0)
            response = self.client.get(url, {'start_time__gte': filter_time})
            self.assertEqual(response.data['count'], 1)
            serializer_dict = self._serialize_wifi_session(ws2, list_single=True)
            self.assertEqual(response.data['results'][0], serializer_dict)
            response = self.client.get(url, {'start_time__lt': filter_time})
            serializer_dict = self._serialize_wifi_session(ws1, list_single=True)
            self.assertEqual(response.data['results'][0], serializer_dict)
            response = self.client.get(url, {'start_time__lte': filter_time})
            self.assertEqual(response.data['count'], 2)
            serializer_dict = self._serialize_wifi_session(wifi_session_qs, many=True)
            self.assertEqual(response.data['results'], serializer_dict)

        with self.subTest('Test filtering using stop time'):
            ws2.stop_time = timezone.now()
            ws2.save()
            ws1.stop_time = timezone.now()
            ws1.save()
            filter_time = ws2.stop_time
            url = reverse('monitoring:api_wifi_session_list')
            wifi_session_qs = WifiSession.objects.order_by('-start_time')
            response = self.client.get(url, {'stop_time': filter_time})
            self.assertEqual(response.data['count'], 1)
            serializer_dict = self._serialize_wifi_session(ws2, list_single=True)
            self.assertEqual(response.data['results'][0], serializer_dict)
            response = self.client.get(url, {'stop_time__gt': filter_time})
            self.assertEqual(response.data['count'], 1)
            serializer_dict = self._serialize_wifi_session(ws1, list_single=True)
            self.assertEqual(response.data['results'][0], serializer_dict)
            response = self.client.get(url, {'stop_time__gte': filter_time})
            self.assertEqual(response.data['count'], 2)
            serializer_dict = self._serialize_wifi_session(wifi_session_qs, many=True)
            self.assertEqual(response.data['results'], serializer_dict)
            response = self.client.get(url, {'stop_time__lt': filter_time})
            self.assertEqual(response.data['count'], 0)
            response = self.client.get(url, {'stop_time__lte': filter_time})
            self.assertEqual(response.data['count'], 1)
            serializer_dict = self._serialize_wifi_session(ws2, list_single=True)
            self.assertEqual(response.data['results'][0], serializer_dict)

    def test_wifi_session_list_detail_multitenancy(self):
        org1, org2, d1, d2, dg1, dg2, ws1, ws2 = self._create_wifi_session_multi_env()
        org1_manager = self._create_operator(
            organizations=[org1],
            username='org1_manager',
            email='orgmanager@test.com',
        )
        org1_member = self._create_operator(
            username='org1_member', email='orgmember@test.com'
        )
        org1_admin = self._create_operator(
            username='org_admin', email='org_admin@test.com', is_superuser=True
        )

        with self.subTest('Test wifi session list org manager'):
            self.client.force_login(org1_manager)
            url = reverse('monitoring:api_wifi_session_list')
            with self.assertNumQueries(5):
                response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['count'], 1)
            serializer_dict = self._serialize_wifi_session(ws1, list_single=True)
            self.assertEqual(response.data['results'][0], serializer_dict)

        with self.subTest('Test wifi session detail org manager'):
            self.client.force_login(org1_manager)
            url = reverse('monitoring:api_wifi_session_detail', args=[ws1.id])
            with self.assertNumQueries(4):
                response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            serializer_dict = self._serialize_wifi_session(ws1)
            self.assertEqual(response.data, serializer_dict)
            # Make sure the WiFi session belonging to org2 is not accessible
            url = reverse('monitoring:api_wifi_session_detail', args=[ws2.pk])
            with self.assertNumQueries(4):
                response = self.client.get(url)
            self.assertEqual(response.status_code, 404)

        with self.subTest('Test wifi session list org member (403 forbidden)'):
            self.client.force_login(org1_member)
            url = reverse('monitoring:api_wifi_session_list')
            err = 'User is not a manager of the organization'
            with self.assertNumQueries(1):
                response = self.client.get(url)
            self.assertEqual(response.status_code, 403)
            self.assertIn(err, response.json()['detail'])

        with self.subTest('Test wifi session detail org member (403 forbidden)'):
            self.client.force_login(org1_member)
            url = reverse('monitoring:api_wifi_session_detail', args=[ws1.pk])
            err = 'User is not a manager of the organization'
            with self.assertNumQueries(1):
                response = self.client.get(url)
            self.assertEqual(response.status_code, 403)
            self.assertIn(err, response.json()['detail'])
            url = reverse('monitoring:api_wifi_session_detail', args=[ws2.pk])
            with self.assertNumQueries(1):
                r = self.client.get(url)
            self.assertEqual(response.status_code, 403)
            self.assertIn(err, response.json()['detail'])

        with self.subTest('Test upgrade operation list org admin'):
            # Superuser (org1_admin) can view
            # wifi sessions of both organizations
            self.client.force_login(org1_admin)
            wifi_session_qs = WifiSession.objects.order_by('-start_time')
            url = reverse('monitoring:api_wifi_session_list')
            with self.assertNumQueries(3):
                r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            serializer_list = self._serialize_wifi_session(wifi_session_qs, many=True)
            self.assertEqual(r.data['results'], serializer_list)
            url = reverse('monitoring:api_wifi_session_list')
            with self.assertNumQueries(3):
                r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            serializer_list = self._serialize_wifi_session(wifi_session_qs, many=True)
            self.assertEqual(r.data['results'], serializer_list)
            # Ensure similar results for wifi_session detail
            url = reverse('monitoring:api_wifi_session_detail', args=[ws1.pk])
            with self.assertNumQueries(2):
                r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            serializer_dict = self._serialize_wifi_session(ws1)
            self.assertEqual(r.data, serializer_dict)
            url = reverse('monitoring:api_wifi_session_detail', args=[ws2.pk])
            with self.assertNumQueries(2):
                r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            serializer_dict = self._serialize_wifi_session(ws2)
            self.assertEqual(r.data, serializer_dict)
