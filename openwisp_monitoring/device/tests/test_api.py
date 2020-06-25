from contextlib import redirect_stderr
from io import StringIO
from unittest.mock import patch

from swapper import load_model

from openwisp_utils.tests import catch_signal

from ... import settings as monitoring_settings
from ..signals import device_metrics_received
from . import DeviceMonitoringTestCase

Chart = load_model('monitoring', 'Chart')
Metric = load_model('monitoring', 'Metric')
DeviceData = load_model('device_monitoring', 'DeviceData')


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
        self.create_test_adata(no_resources=True)

    def test_200_traffic_counter_incremented(self):
        dd = self.create_test_adata(no_resources=True)
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
        self.assertEqual(Metric.objects.count(), 6)
        self.assertEqual(Chart.objects.count(), 4)
        if_dict = {'wlan0': data2['interfaces'][0], 'wlan1': data2['interfaces'][1]}
        for ifname in ['wlan0', 'wlan1']:
            iface = if_dict[ifname]
            for field_name in ['rx_bytes', 'tx_bytes']:
                m = Metric.objects.get(
                    key=ifname, field_name=field_name, object_id=d.pk
                )
                points = m.read(limit=10, order='-time')
                self.assertEqual(len(points), 2)
                expected = iface['statistics'][field_name] - points[1][m.field_name]
                self.assertEqual(points[0][m.field_name], expected)
            m = Metric.objects.get(key=ifname, field_name='clients', object_id=d.pk)
            points = m.read(limit=10, order='-time')
            self.assertEqual(len(points), len(iface['wireless']['clients']) * 2)

    def test_200_traffic_counter_reset(self):
        dd = self.create_test_adata(no_resources=True)
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
        self.assertEqual(Metric.objects.count(), 6)
        self.assertEqual(Chart.objects.count(), 4)
        if_dict = {'wlan0': data2['interfaces'][0], 'wlan1': data2['interfaces'][1]}
        for ifname in ['wlan0', 'wlan1']:
            iface = if_dict[ifname]
            for field_name in ['rx_bytes', 'tx_bytes']:
                m = Metric.objects.get(
                    key=ifname, field_name=field_name, object_id=d.pk
                )
                points = m.read(limit=10, order='-time')
                self.assertEqual(len(points), 2)
                expected = iface['statistics'][field_name]
                self.assertEqual(points[0][m.field_name], expected)
            m = Metric.objects.get(key=ifname, field_name='clients', object_id=d.pk)
            points = m.read(limit=10, order='-time')
            self.assertEqual(len(points), len(iface['wireless']['clients']) * 2)

    def test_200_multiple_measurements(self):
        dd = self._create_multiple_measurements(no_resources=True)
        self.assertEqual(Metric.objects.count(), 6)
        self.assertEqual(Chart.objects.count(), 4)
        expected = {
            'wlan0': {'rx_bytes': 10000, 'tx_bytes': 6000},
            'wlan1': {'rx_bytes': 4587, 'tx_bytes': 2993},
        }
        # wlan0 rx_bytes
        m = Metric.objects.get(key='wlan0', field_name='rx_bytes', object_id=dd.pk)
        points = m.read(limit=10, order='-time')
        self.assertEqual(len(points), 4)
        expected = [700000000, 100000000, 399999676, 324]
        for i, point in enumerate(points):
            self.assertEqual(point['rx_bytes'], expected[i])
        # wlan0 tx_bytes
        m = Metric.objects.get(key='wlan0', field_name='tx_bytes', object_id=dd.pk)
        points = m.read(limit=10, order='-time')
        self.assertEqual(len(points), 4)
        expected = [300000000, 200000000, 99999855, 145]
        for i, point in enumerate(points):
            self.assertEqual(point['tx_bytes'], expected[i])
        c = m.chart_set.first()
        data = c.read()
        # expected download wlan0
        self.assertEqual(data['traces'][0][1][-1], 1.2)
        # expected upload wlan0
        self.assertEqual(data['traces'][1][1][-1], 0.6)
        # wlan1 rx_bytes
        m = Metric.objects.get(key='wlan1', field_name='rx_bytes', object_id=dd.pk)
        points = m.read(limit=10, order='-time')
        self.assertEqual(len(points), 4)
        expected = [1000000000, 0, 1999997725, 2275]
        for i, point in enumerate(points):
            self.assertEqual(point['rx_bytes'], expected[i])
        # wlan1 tx_bytes
        m = Metric.objects.get(key='wlan1', field_name='tx_bytes', object_id=dd.pk)
        points = m.read(limit=10, order='-time')
        self.assertEqual(len(points), 4)
        expected = [500000000, 0, 999999174, 826]
        for i, point in enumerate(points):
            self.assertEqual(point['tx_bytes'], expected[i])
        c = m.chart_set.first()
        data = c.read()
        # expected download wlan1
        self.assertEqual(data['traces'][0][1][-1], 3.0)
        # expected upload wlan1
        self.assertEqual(data['traces'][1][1][-1], 1.5)

    def test_garbage_clients(self):
        o = self._create_org()
        d = self._create_device(organization=o)
        r = self._post_data(
            d.id,
            d.key,
            {
                'type': 'DeviceMonitoring',
                'interfaces': [
                    {'name': 'garbage1', 'wireless': {'clients': {}}},
                    {
                        'name': 'garbage2',
                        'wireless': {'clients': [{'what?': 'mac missing'}]},
                    },
                    {'name': 'garbage3', 'wireless': {}},
                    {'name': 'garbage4'},
                ],
            },
        )
        self.assertEqual(r.status_code, 400)

    @patch.object(monitoring_settings, 'AUTO_CHARTS', return_value=[])
    def test_auto_chart_disabled(self, *args):
        self.assertEqual(Chart.objects.count(), 0)
        o = self._create_org()
        d = self._create_device(organization=o)
        self._post_data(d.id, d.key, self._data())
        self.assertEqual(Chart.objects.count(), 0)

    def test_get_device_metrics_200(self):
        dd = self.create_test_adata()
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
        dd = self.create_test_adata()
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
        m = self._create_object_metric(content_object=d, name='applications')
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
                '2',
                '1',
                '9.73',
                '0',
                '8.27',
            ],
        )
        self.assertEqual(rows[-4].strip(), '')
        self.assertEqual(rows[-3].strip(), 'Histogram')
        self.assertEqual(rows[-2].strip().split(','), ['ssh', '100'])
        self.assertEqual(rows[-1].strip().split(','), ['http2', '90'])

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
        dd = self.create_test_adata(no_resources=True)
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
        self._create_object_metric(
            name='ping', key='ping', field_name='reachable', content_object=d
        )
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
        # Tests if chart_config is invalid, then it is skipped and not failed
        d = self._create_device(organization=self._create_org())
        m = self._create_object_metric(name='test_metric', content_object=d)
        c = self._create_chart(metric=m, test_data=None)
        with redirect_stderr(StringIO()) as stderr:
            c.configuration = 'invalid'
            c.save()
            r = self.client.get(self._url(d.pk.hex, d.key))
        self.assertIn('InvalidChartConfigException', stderr.getvalue())
        self.assertEqual(r.status_code, 200)

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
            self.assertAlmostEqual(metric_data['percent_used'], 0.09729, places=5)
            self.assertIsNone(metric_data.get('available_memory'))
            self.assertEqual(r.status_code, 200)
        with self.subTest('Test when available memory is less than free memory'):
            data['resources']['memory']['available'] = 2232664
            r = self._post_data(d.id, d.key, data)
            metric_data = m.read(order='-time', extra_fields='*')[0]
            self.assertAlmostEqual(metric_data['percent_used'], 0.09729, places=5)
            self.assertEqual(metric_data['available_memory'], 2232664)
            self.assertEqual(r.status_code, 200)
        with self.subTest('Test when available memory is greater than free memory'):
            data['resources']['memory']['available'] = 225567664
            r = self._post_data(d.id, d.key, data)
            m = Metric.objects.get(key='memory')
            metric_data = m.read(order='-time', extra_fields='*')[0]
            self.assertAlmostEqual(metric_data['percent_used'], 0.09301, places=5)
            self.assertEqual(metric_data['available_memory'], 225567664)
            self.assertEqual(r.status_code, 200)

    def test_get_device_status_200(self):
        dd = self.create_test_adata(no_resources=True)
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
