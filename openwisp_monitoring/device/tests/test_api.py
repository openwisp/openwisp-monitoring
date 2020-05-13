from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse

from openwisp_utils.tests import catch_signal

from ... import settings as monitoring_settings
from ...device.signals import device_metrics_received
from ...monitoring.models import Graph, Metric
from ..models import DeviceData
from . import DeviceMonitoringTestCase


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
        self.assertEqual(Graph.objects.count(), 0)
        data = {'type': 'DeviceMonitoring'}
        r = self._post_data(d.id, d.key, data)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Metric.objects.count(), 0)
        self.assertEqual(Graph.objects.count(), 0)

    def test_200_create(self):
        o = self._create_org()
        d = self._create_device(organization=o)
        data = self._data()
        r = self._post_data(d.id, d.key, data)
        self.assertEqual(r.status_code, 200)
        dd = DeviceData(pk=d.pk)
        self.assertDictEqual(dd.data, data)
        self.assertEqual(Metric.objects.count(), 6)
        self.assertEqual(Graph.objects.count(), 4)
        if_dict = {'wlan0': data['interfaces'][0], 'wlan1': data['interfaces'][1]}
        for ifname in ['wlan0', 'wlan1']:
            iface = if_dict[ifname]
            for field_name in ['rx_bytes', 'tx_bytes']:
                m = Metric.objects.get(
                    key=ifname, field_name=field_name, object_id=d.pk
                )
                points = m.read(limit=10, order='time DESC')
                self.assertEqual(len(points), 1)
                self.assertEqual(
                    points[0][m.field_name], iface['statistics'][field_name]
                )
            m = Metric.objects.get(key=ifname, field_name='clients', object_id=d.pk)
            points = m.read(limit=10, order='time DESC')
            self.assertEqual(len(points), len(iface['wireless']['clients']))

    def test_200_traffic_counter_incremented(self):
        self.test_200_create()
        self.assertEqual(self.device_model.objects.count(), 1)
        d = self.device_model.objects.first()
        data2 = self._data()
        data2['interfaces'][0]['statistics']['rx_bytes'] = 983
        data2['interfaces'][0]['statistics']['tx_bytes'] = 1567
        data2['interfaces'][1]['statistics']['rx_bytes'] = 2983
        data2['interfaces'][1]['statistics']['tx_bytes'] = 4567
        r = self._post_data(d.id, d.key, data2)
        self.assertEqual(r.status_code, 200)
        dd = DeviceData(pk=d.pk)
        self.assertDictEqual(dd.data, data2)
        self.assertEqual(Metric.objects.count(), 6)
        self.assertEqual(Graph.objects.count(), 4)
        if_dict = {'wlan0': data2['interfaces'][0], 'wlan1': data2['interfaces'][1]}
        for ifname in ['wlan0', 'wlan1']:
            iface = if_dict[ifname]
            for field_name in ['rx_bytes', 'tx_bytes']:
                m = Metric.objects.get(
                    key=ifname, field_name=field_name, object_id=d.pk
                )
                points = m.read(limit=10, order='time DESC')
                self.assertEqual(len(points), 2)
                expected = iface['statistics'][field_name] - points[1][m.field_name]
                self.assertEqual(points[0][m.field_name], expected)
            m = Metric.objects.get(key=ifname, field_name='clients', object_id=d.pk)
            points = m.read(limit=10, order='time DESC')
            self.assertEqual(len(points), len(iface['wireless']['clients']) * 2)

    def test_200_traffic_counter_reset(self):
        self.test_200_create()
        self.assertEqual(self.device_model.objects.count(), 1)
        d = self.device_model.objects.first()
        data2 = self._data()
        data2['interfaces'][0]['statistics']['rx_bytes'] = 50
        data2['interfaces'][0]['statistics']['tx_bytes'] = 20
        data2['interfaces'][1]['statistics']['rx_bytes'] = 80
        data2['interfaces'][1]['statistics']['tx_bytes'] = 120
        r = self._post_data(d.id, d.key, data2)
        self.assertEqual(r.status_code, 200)
        dd = DeviceData(pk=d.pk)
        self.assertDictEqual(dd.data, data2)
        self.assertEqual(Metric.objects.count(), 6)
        self.assertEqual(Graph.objects.count(), 4)
        if_dict = {'wlan0': data2['interfaces'][0], 'wlan1': data2['interfaces'][1]}
        for ifname in ['wlan0', 'wlan1']:
            iface = if_dict[ifname]
            for field_name in ['rx_bytes', 'tx_bytes']:
                m = Metric.objects.get(
                    key=ifname, field_name=field_name, object_id=d.pk
                )
                points = m.read(limit=10, order='time DESC')
                self.assertEqual(len(points), 2)
                expected = iface['statistics'][field_name]
                self.assertEqual(points[0][m.field_name], expected)
            m = Metric.objects.get(key=ifname, field_name='clients', object_id=d.pk)
            points = m.read(limit=10, order='time DESC')
            self.assertEqual(len(points), len(iface['wireless']['clients']) * 2)

    def _create_multiple_measurements(self, create=True):
        if create:
            self.test_200_create()
        self.assertEqual(self.device_model.objects.count(), 1)
        d = self.device_model.objects.first()
        data2 = self._data()
        data2['interfaces'][0]['statistics']['rx_bytes'] = 400000000
        data2['interfaces'][0]['statistics']['tx_bytes'] = 100000000
        data2['interfaces'][1]['statistics']['rx_bytes'] = 2000000000
        data2['interfaces'][1]['statistics']['tx_bytes'] = 1000000000
        r = self._post_data(d.id, d.key, data2)
        data3 = self._data()
        data3['interfaces'][0]['statistics']['rx_bytes'] = 500000000
        data3['interfaces'][0]['statistics']['tx_bytes'] = 300000000
        data3['interfaces'][1]['statistics']['rx_bytes'] = 0
        data3['interfaces'][1]['statistics']['tx_bytes'] = 0
        r = self._post_data(d.id, d.key, data3)
        data4 = self._data()
        data4['interfaces'][0]['statistics']['rx_bytes'] = 1200000000
        data4['interfaces'][0]['statistics']['tx_bytes'] = 600000000
        data4['interfaces'][1]['statistics']['rx_bytes'] = 1000000000
        data4['interfaces'][1]['statistics']['tx_bytes'] = 500000000
        r = self._post_data(d.id, d.key, data4)
        self.assertEqual(r.status_code, 200)
        dd = DeviceData(pk=d.pk)
        self.assertDictEqual(dd.data, data4)
        return dd

    def test_200_multiple_measurements(self):
        dd = self._create_multiple_measurements()
        self.assertEqual(Metric.objects.count(), 6)
        self.assertEqual(Graph.objects.count(), 4)
        expected = {
            'wlan0': {'rx_bytes': 10000, 'tx_bytes': 6000},
            'wlan1': {'rx_bytes': 4587, 'tx_bytes': 2993},
        }
        # wlan0 rx_bytes
        m = Metric.objects.get(key='wlan0', field_name='rx_bytes', object_id=dd.pk)
        points = m.read(limit=10, order='time DESC')
        self.assertEqual(len(points), 4)
        expected = [700000000, 100000000, 399999676, 324]
        for i, point in enumerate(points):
            self.assertEqual(point['rx_bytes'], expected[i])
        # wlan0 tx_bytes
        m = Metric.objects.get(key='wlan0', field_name='tx_bytes', object_id=dd.pk)
        points = m.read(limit=10, order='time DESC')
        self.assertEqual(len(points), 4)
        expected = [300000000, 200000000, 99999855, 145]
        for i, point in enumerate(points):
            self.assertEqual(point['tx_bytes'], expected[i])
        g = m.graph_set.first()
        data = g.read()
        # expected download wlan0
        self.assertEqual(data['traces'][0][1][-1], 1.2)
        # expected upload wlan0
        self.assertEqual(data['traces'][1][1][-1], 0.6)
        # wlan1 rx_bytes
        m = Metric.objects.get(key='wlan1', field_name='rx_bytes', object_id=dd.pk)
        points = m.read(limit=10, order='time DESC')
        self.assertEqual(len(points), 4)
        expected = [1000000000, 0, 1999997725, 2275]
        for i, point in enumerate(points):
            self.assertEqual(point['rx_bytes'], expected[i])
        # wlan1 tx_bytes
        m = Metric.objects.get(key='wlan1', field_name='tx_bytes', object_id=dd.pk)
        points = m.read(limit=10, order='time DESC')
        self.assertEqual(len(points), 4)
        expected = [500000000, 0, 999999174, 826]
        for i, point in enumerate(points):
            self.assertEqual(point['tx_bytes'], expected[i])
        g = m.graph_set.first()
        data = g.read()
        # expected download wlan1
        self.assertEqual(data['traces'][0][1][-1], 3.0)
        # expected upload wlan1
        self.assertEqual(data['traces'][1][1][-1], 1.5)

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

    @patch.object(monitoring_settings, 'AUTO_GRAPHS', return_value=[])
    def test_auto_graph_disabled(self, *args):
        self.assertEqual(Graph.objects.count(), 0)
        o = self._create_org()
        d = self._create_device(organization=o)
        self._post_data(d.id, d.key, self._data())
        self.assertEqual(Graph.objects.count(), 0)

    def test_get_device_metrics_200(self):
        dd = self._create_multiple_measurements()
        d = self.device_model.objects.get(pk=dd.pk)
        r = self.client.get(self._url(d.pk.hex, d.key))
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.data['graphs'], list)
        self.assertEqual(len(r.data['graphs']), 4)
        self.assertIn('x', r.data)
        graphs = r.data['graphs']
        for graph in graphs:
            self.assertIn('traces', graph)
            self.assertIn('title', graph)
            self.assertIn('description', graph)
            self.assertIn('type', graph)
            self.assertIn('summary', graph)
            self.assertIsInstance(graph['summary'], dict)
            self.assertIn('summary_labels', graph)
            self.assertIsInstance(graph['summary_labels'], list)
            self.assertIn('unit', graph)
            self.assertIn('colors', graph)
            self.assertIn('colorscale', graph)
        # test order
        self.assertEqual(graphs[0]['title'], 'WiFi clients: wlan0')
        self.assertEqual(graphs[1]['title'], 'WiFi clients: wlan1')
        self.assertEqual(graphs[2]['title'], 'Traffic: wlan0')
        self.assertEqual(graphs[3]['title'], 'Traffic: wlan1')

    def test_get_device_metrics_histogram_ignore_x(self):
        o = self._create_org()
        d = self._create_device(organization=o)
        m = self._create_object_metric(content_object=d, name='applications')
        self._create_graph(metric=m, configuration='histogram')
        self._create_multiple_measurements(create=False)
        r = self.client.get(self._url(d.pk.hex, d.key))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(len(r.data['x']) > 50)

    def test_get_device_metrics_1d(self):
        dd = self._create_multiple_measurements()
        d = self.device_model.objects.get(pk=dd.pk)
        r = self.client.get('{0}&time=1d'.format(self._url(d.pk, d.key)))
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.data['graphs'], list)

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
        dd = self._create_multiple_measurements()
        d = self.device_model.objects.get(pk=dd.pk)
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
            ],
        )
        last_line = rows[-1].strip().split(',')
        self.assertEqual(last_line, [last_line[0], '1', '2', '1.2', '0.6', '3', '1.5'])

    def test_get_device_metrics_400_bad_timezone(self):
        dd = self._create_multiple_measurements()
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

    # testing admin here is more convenient because
    # we already have the code that creates test data

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
