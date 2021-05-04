from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from swapper import load_model

from openwisp_controller.geo.tests.utils import TestGeoMixin
from openwisp_utils.tests import catch_signal

from ... import settings as monitoring_settings
from ..signals import device_metrics_received
from . import DeviceMonitoringTestCase

Chart = load_model('monitoring', 'Chart')
Metric = load_model('monitoring', 'Metric')
DeviceData = load_model('device_monitoring', 'DeviceData')
# needed for config.geo
Device = load_model('config', 'Device')
DeviceLocation = load_model('geo', 'DeviceLocation')
Location = load_model('geo', 'Location')


class TestDeviceApi(DeviceMonitoringTestCase):
    """
    Tests API (device metric collection)
    """

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
        r = self._post_data(d.id, d.key, {'type': 'wrong'})
        self.assertEqual(r.status_code, 400)
        r = self._post_data(
            d.id, d.key, {'type': 'DeviceMonitoring', 'interfaces': [{}]}
        )
        self.assertEqual(r.status_code, 400)

    def test_200_none(self):
        o = self._create_org()
        d = self._create_device(organization=o)
        data = {'type': 'DeviceMonitoring', 'interfaces': []}
        r = self._post_data(d.id, d.key, data)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Metric.objects.count(), 0)
        self.assertEqual(Chart.objects.count(), 0)
        data = {'type': 'DeviceMonitoring'}
        r = self._post_data(d.id, d.key, data)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Metric.objects.count(), 0)
        self.assertEqual(Chart.objects.count(), 0)

    def test_200_create(self):
        self.create_test_data(no_resources=True)

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
        self.assertDictEqual(dd.data, data2)
        self.assertEqual(Metric.objects.count(), 4)
        self.assertEqual(Chart.objects.count(), 4)
        if_dict = {'wlan0': data2['interfaces'][0], 'wlan1': data2['interfaces'][1]}
        for ifname in ['wlan0', 'wlan1']:
            iface = if_dict[ifname]
            m = Metric.objects.get(key=ifname, field_name='rx_bytes', object_id=d.pk)
            points = m.read(limit=10, order='-time', extra_fields=['tx_bytes'])
            self.assertEqual(len(points), 2)
            for field in ['rx_bytes', 'tx_bytes']:
                expected = iface['statistics'][field] - points[1][field]
                self.assertEqual(points[0][field], expected)
            m = Metric.objects.get(key=ifname, field_name='clients', object_id=d.pk)
            points = m.read(limit=10, order='-time')
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
        self.assertDictEqual(dd.data, data2)
        self.assertEqual(Metric.objects.count(), 4)
        self.assertEqual(Chart.objects.count(), 4)
        if_dict = {'wlan0': data2['interfaces'][0], 'wlan1': data2['interfaces'][1]}
        for ifname in ['wlan0', 'wlan1']:
            iface = if_dict[ifname]
            m = Metric.objects.get(key=ifname, field_name='rx_bytes', object_id=d.pk)
            points = m.read(limit=10, order='-time', extra_fields=['tx_bytes'])
            self.assertEqual(len(points), 2)
            for field in ['rx_bytes', 'tx_bytes']:
                expected = iface['statistics'][field]
                self.assertEqual(points[0][field], expected)
            m = Metric.objects.get(key=ifname, field_name='clients', object_id=d.pk)
            points = m.read(limit=10, order='-time')
            self.assertEqual(len(points), len(iface['wireless']['clients']) * 2)

    def test_200_multiple_measurements(self):
        dd = self._create_multiple_measurements(no_resources=True)
        self.assertEqual(Metric.objects.count(), 4)
        self.assertEqual(Chart.objects.count(), 4)
        expected = {
            'wlan0': {'rx_bytes': 10000, 'tx_bytes': 6000},
            'wlan1': {'rx_bytes': 4587, 'tx_bytes': 2993},
        }
        # wlan0 traffic
        m = Metric.objects.get(key='wlan0', field_name='rx_bytes', object_id=dd.pk)
        points = m.read(limit=10, order='-time', extra_fields=['tx_bytes'])
        self.assertEqual(len(points), 4)
        expected = [700000000, 100000000, 399999676, 324]
        for i, point in enumerate(points):
            self.assertEqual(point['rx_bytes'], expected[i])
        expected = [300000000, 200000000, 99999855, 145]
        for i, point in enumerate(points):
            self.assertEqual(point['tx_bytes'], expected[i])
        c = m.chart_set.first()
        data = c.read()
        # expected download wlan0
        self.assertEqual(data['traces'][0][1][-1], 1.2)
        # expected upload wlan0
        self.assertEqual(data['traces'][1][1][-1], 0.6)
        # wlan1 traffic
        m = Metric.objects.get(key='wlan1', field_name='rx_bytes', object_id=dd.pk)
        points = m.read(limit=10, order='-time', extra_fields=['tx_bytes'])
        self.assertEqual(len(points), 4)
        expected = [1000000000, 0, 1999997725, 2275]
        for i, point in enumerate(points):
            self.assertEqual(point['rx_bytes'], expected[i])
        expected = [500000000, 0, 999999174, 826]
        for i, point in enumerate(points):
            self.assertEqual(point['tx_bytes'], expected[i])
        c = m.chart_set.first()
        data = c.read()
        # expected download wlan1
        self.assertEqual(data['traces'][0][1][-1], 3.0)
        # expected upload wlan1
        self.assertEqual(data['traces'][1][1][-1], 1.5)

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
        self.assertEqual(Chart.objects.count(), 0)
        o = self._create_org()
        d = self._create_device(organization=o)
        self._post_data(d.id, d.key, self._data())
        self.assertEqual(Chart.objects.count(), 0)

    def test_get_device_metrics_200(self):
        dd = self.create_test_data()
        d = self.device_model.objects.get(pk=dd.pk)
        r = self.client.get(self._url(d.pk.hex, d.key))
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.data['charts'], list)
        self.assertEqual(len(r.data['charts']), 7)
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
        # test order
        self.assertEqual(charts[0]['title'], 'WiFi clients: wlan0')
        self.assertEqual(charts[1]['title'], 'WiFi clients: wlan1')
        self.assertEqual(charts[2]['title'], 'Traffic: wlan0')
        self.assertEqual(charts[3]['title'], 'Traffic: wlan1')
        self.assertEqual(charts[4]['title'], 'Memory Usage')
        self.assertEqual(charts[5]['title'], 'CPU Load')
        self.assertEqual(charts[6]['title'], 'Disk Usage')

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

    def test_get_device_metrics_403(self):
        d = self._create_device(organization=self._create_org())
        r = self.client.get(self._url(d.pk))
        self.assertEqual(r.status_code, 403)

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
            self.assertEqual(c.read(), mock)
            r = self.client.get('{0}&csv=1'.format(self._url(d.pk, d.key)))
        self.assertEqual(r.get('Content-Disposition'), 'attachment; filename=data.csv')
        self.assertEqual(r.get('Content-Type'), 'text/csv')
        rows = r.content.decode('utf8').strip().split('\n')
        self.assertEqual(rows[-2].strip().split(','), ['http2', '100'])
        self.assertEqual(rows[-1].strip().split(','), ['ssh', '0'])

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
        with catch_signal(device_metrics_received) as handler:
            response = self._post_data(d.id, d.key, data)
        request = response.renderer_context['request']
        handler.assert_called_once_with(
            instance=dd,
            request=request,
            sender=DeviceData,
            signal=device_metrics_received,
        )

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
            m = Metric.objects.get(key='memory')
            metric_data = m.read(order='-time', extra_fields='*')[0]
            self.assertEqual(metric_data['percent_used'], 9.729419481797308)
            self.assertIsNone(metric_data.get('available_memory'))
            self.assertEqual(r.status_code, 200)
        with self.subTest('Test when available memory is less than free memory'):
            data['resources']['memory']['available'] = 2232664
            r = self._post_data(d.id, d.key, data)
            metric_data = m.read(order='-time', extra_fields='*')[0]
            self.assertEqual(metric_data['percent_used'], 9.729419481797308)
            self.assertEqual(metric_data['available_memory'], 2232664)
            self.assertEqual(r.status_code, 200)
        with self.subTest('Test when available memory is greater than free memory'):
            data['resources']['memory']['available'] = 225567664
            r = self._post_data(d.id, d.key, data)
            m = Metric.objects.get(key='memory')
            metric_data = m.read(order='-time', extra_fields='*')[0]
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
        charts_count = Chart.objects.count()
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
        self.assertEqual(charts[2]['summary']['access_tech'], 3.0)
        # ensure correct color-coding
        self.assertEqual(
            charts[2]['colorscale']['map'],
            [
                [4, '#b42a0c', 'umts'],
                [3, '#25b262', 'lte'],
                [2, '#df7514', 'gsm'],
                [1, '#efdd50', 'evdo'],
                [0, '#0e7371', 'cdma1x'],
            ],
        )
        self.assertEqual(Chart.objects.count(), charts_count + 3)


class TestGeoApi(TestGeoMixin, DeviceMonitoringTestCase):
    location_model = Location
    object_location_model = DeviceLocation
    object_model = Device

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
