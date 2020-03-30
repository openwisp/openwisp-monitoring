import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory

from ... import settings as monitoring_settings
from ...monitoring.models import Graph, Metric
from ..api import views
from ..models import DeviceData
from . import DeviceMonitoringTestCase
from .mock import mock_data, mock_histogram_data, mock_metric_view


class TestDeviceApi(DeviceMonitoringTestCase):
    """
    Tests API (device metric collection)
    """
    def _url(self, pk, key=None):
        url = reverse('monitoring:api_device_metric', args=[pk])
        if key:
            url = '{0}?key={1}'.format(url, key)
        return url

    @patch.object(views, 'device_metric', side_effect=mock_metric_view)
    def _post_data(self, id, key, data, mock_device_metric, mock=True):
        url = self._url(id, key)
        netjson = json.dumps(data)
        if mock:
            request = APIRequestFactory().post(url, netjson, content_type='application/json')
            d = self.device_model.objects.get(id=id)
            r = views.device_metric(request, data, d.pk)
            return r
        else:
            return self.client.post(url, netjson, content_type='application/json')

    def _data(self):
        return {
            'type': 'DeviceMonitoring',
            'interfaces': [
                {
                    'name': 'wlan0',
                    'statistics': {
                        'rx_bytes': 324,
                        'tx_bytes': 145,
                        'collisions': 0,
                        'multicast': 0,
                        'rx_dropped': 0,
                        'tx_dropped': 0,
                    },
                    'wireless': {
                        'frequency': 2437,
                        'mode': 'access_point',
                        'signal': -29,
                        'tx_power': 6,
                        'channel': 6,
                        'ssid': 'testnet',
                        'noise': -95,
                        'country': 'US',
                        'clients': [
                            {
                                'mac': '00:ee:ad:34:f5:3b',
                                'wps': False,
                                'wds': False,
                                'ht': True,
                                'preauth': False,
                                'assoc': True,
                                'authorized': True,
                                'vht': False,
                                'wmm': True,
                                'aid': 1,
                                'mfp': False,
                                'auth': True
                            }
                        ]
                    }
                },
                {
                    'name': 'wlan1',
                    'statistics': {
                        'rx_bytes': 2275,
                        'tx_bytes': 826,
                        'collisions': 0,
                        'multicast': 0,
                        'rx_dropped': 0,
                        'tx_dropped': 0,
                    },
                    'wireless': {
                        'frequency': 2437,
                        'mode': 'access_point',
                        'signal': -29,
                        'tx_power': 6,
                        'channel': 6,
                        'ssid': 'testnet',
                        'noise': -95,
                        'country': 'US',
                        'clients': [
                            {
                                'mac': 'b0:e1:7e:30:16:44',
                                'wps': False,
                                'wds': False,
                                'ht': True,
                                'preauth': False,
                                'assoc': True,
                                'authorized': True,
                                'vht': False,
                                'wmm': True,
                                'aid': 1,
                                'mfp': False,
                                'auth': True
                            },
                            {
                                'mac': 'c0:ee:fb:34:f5:4b',
                                'wps': False,
                                'wds': False,
                                'ht': True,
                                'preauth': False,
                                'assoc': True,
                                'authorized': True,
                                'vht': False,
                                'wmm': True,
                                'aid': 1,
                                'mfp': False,
                                'auth': True
                            }
                        ],
                    },
                }
            ]
        }

    _garbage_clients = {
        'type': 'DeviceMonitoring',
        'interfaces': [
            {
                'name': 'garbage1',
                'wireless': {
                    'clients': {},
                },
            },
            {
                'name': 'garbage2',
                'wireless': {
                    'clients': [
                        {'what?': 'mac missing'}
                    ],
                },
            },
            {
                'name': 'garbage3',
                'wireless': {},
            },
            {
                'name': 'garbage4'
            }
        ]
    }

    def test_404(self):
        r = self._post_data(self.device_model().pk, '123', self._data(), mock=False)
        self.assertEqual(r.status_code, 404)

    def test_403(self):
        o = self._create_org()
        d = self._create_device(organization=o)
        r = self.client.post(self._url(d.pk))
        self.assertEqual(r.status_code, 403)
        r = self._post_data(d.id, 'WRONG', self._data(), mock=False)
        self.assertEqual(r.status_code, 403)

    def test_400(self):
        o = self._create_org()
        d = self._create_device(organization=o)
        r = self._post_data(d.id, d.key, {'interfaces': []}, mock=False)
        self.assertEqual(r.status_code, 400)
        r = self._post_data(d.id, d.key, {'type': 'wrong'}, mock=False)
        self.assertEqual(r.status_code, 400)
        r = self._post_data(d.id, d.key, {
            'type': 'DeviceMonitoring', 'interfaces': [{}]
        }, mock=False)
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

    def test_200_create(self, mock=True):
        o = self._create_org()
        d = self._create_device(organization=o)
        data = self._data()
        if mock:
            r = self._post_data(d.id, d.key, data)
        else:
            r = self._post_data(d.id, d.key, data, mock=False)
            dd = DeviceData(pk=d.pk)
            self.assertDictEqual(dd.data, data)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Metric.objects.count(), 6)
        self.assertEqual(Graph.objects.count(), 4)
        if_dict = {'wlan0': data['interfaces'][0],
                   'wlan1': data['interfaces'][1]}
        for ifname in ['wlan0', 'wlan1']:
            iface = if_dict[ifname]
            for field_name in ['rx_bytes', 'tx_bytes']:
                m = Metric.objects.get(key=ifname, field_name=field_name,
                                       object_id=d.pk)
                points = m.read(limit=10, order='time DESC')
                if mock:
                    pass
                else:
                    self.assertEqual(len(points), 1)
                    self.assertEqual(points[0][m.field_name],
                                     iface['statistics'][field_name])
            m = Metric.objects.get(key=ifname, field_name='clients',
                                   object_id=d.pk)
            points = m.read(limit=10, order='time DESC')
            self.assertEqual(len(points), len(iface['wireless']['clients']))

    def test_200_traffic_counter_incremented(self):
        self.test_200_create(mock=False)
        self.assertEqual(self.device_model.objects.count(), 1)
        d = self.device_model.objects.first()
        data2 = self._data()
        data2['interfaces'][0]['statistics']['rx_bytes'] = 983
        data2['interfaces'][0]['statistics']['tx_bytes'] = 1567
        data2['interfaces'][1]['statistics']['rx_bytes'] = 2983
        data2['interfaces'][1]['statistics']['tx_bytes'] = 4567
        r = self._post_data(d.id, d.key, data2, mock=False)
        self.assertEqual(r.status_code, 200)
        dd = DeviceData(pk=d.pk)
        self.assertDictEqual(dd.data, data2)
        self.assertEqual(Metric.objects.count(), 6)
        self.assertEqual(Graph.objects.count(), 4)
        if_dict = {'wlan0': data2['interfaces'][0],
                   'wlan1': data2['interfaces'][1]}
        for ifname in ['wlan0', 'wlan1']:
            iface = if_dict[ifname]
            for field_name in ['rx_bytes', 'tx_bytes']:
                m = Metric.objects.get(key=ifname, field_name=field_name,
                                       object_id=d.pk)
                points = m.read(limit=10, order='time DESC')
                self.assertEqual(len(points), 2)
                expected = iface['statistics'][field_name] - points[1][m.field_name]
                self.assertEqual(points[0][m.field_name], expected)
            m = Metric.objects.get(key=ifname, field_name='clients',
                                   object_id=d.pk)
            points = m.read(limit=10, order='time DESC')
            self.assertEqual(len(points), len(iface['wireless']['clients']) * 2)

    def test_200_traffic_counter_reset(self):
        self.test_200_create(mock=False)
        self.assertEqual(self.device_model.objects.count(), 1)
        d = self.device_model.objects.first()
        data2 = self._data()
        data2['interfaces'][0]['statistics']['rx_bytes'] = 50
        data2['interfaces'][0]['statistics']['tx_bytes'] = 20
        data2['interfaces'][1]['statistics']['rx_bytes'] = 80
        data2['interfaces'][1]['statistics']['tx_bytes'] = 120
        r = self._post_data(d.id, d.key, data2, mock=False)
        self.assertEqual(r.status_code, 200)
        dd = DeviceData(pk=d.pk)
        self.assertDictEqual(dd.data, data2)
        self.assertEqual(Metric.objects.count(), 6)
        self.assertEqual(Graph.objects.count(), 4)
        if_dict = {'wlan0': data2['interfaces'][0],
                   'wlan1': data2['interfaces'][1]}
        for ifname in ['wlan0', 'wlan1']:
            iface = if_dict[ifname]
            for field_name in ['rx_bytes', 'tx_bytes']:
                m = Metric.objects.get(key=ifname, field_name=field_name,
                                       object_id=d.pk)
                points = m.read(limit=10, order='time DESC')
                self.assertEqual(len(points), 2)
                expected = iface['statistics'][field_name]
                self.assertEqual(points[0][m.field_name], expected)
            m = Metric.objects.get(key=ifname, field_name='clients',
                                   object_id=d.pk)
            points = m.read(limit=10, order='time DESC')
            self.assertEqual(len(points), len(iface['wireless']['clients']) * 2)

    def _create_multiple_measurements(self, create=True, mock=True):
        if create:
            self.test_200_create(mock)
        self.assertEqual(self.device_model.objects.count(), 1)
        d = self.device_model.objects.first()
        data2 = self._data()
        data2['interfaces'][0]['statistics']['rx_bytes'] = 400000000
        data2['interfaces'][0]['statistics']['tx_bytes'] = 100000000
        data2['interfaces'][1]['statistics']['rx_bytes'] = 2000000000
        data2['interfaces'][1]['statistics']['tx_bytes'] = 1000000000
        r = self._post_data(d.id, d.key, data2, mock=mock)
        data3 = self._data()
        data3['interfaces'][0]['statistics']['rx_bytes'] = 500000000
        data3['interfaces'][0]['statistics']['tx_bytes'] = 300000000
        data3['interfaces'][1]['statistics']['rx_bytes'] = 0
        data3['interfaces'][1]['statistics']['tx_bytes'] = 0
        r = self._post_data(d.id, d.key, data3, mock=mock)
        data4 = self._data()
        data4['interfaces'][0]['statistics']['rx_bytes'] = 1200000000
        data4['interfaces'][0]['statistics']['tx_bytes'] = 600000000
        data4['interfaces'][1]['statistics']['rx_bytes'] = 1000000000
        data4['interfaces'][1]['statistics']['tx_bytes'] = 500000000
        r = self._post_data(d.id, d.key, data4, mock=mock)
        self.assertEqual(r.status_code, 200)
        dd = DeviceData(pk=d.pk)
        if not mock:
            self.assertDictEqual(dd.data, data4)
        return dd

    def _create_single_measurement(self, create=True):
        o = self._create_org()
        d = self._create_device(organization=o)
        dd = DeviceData(pk=d.pk)
        data = self._data()
        data['interfaces'][0]['statistics']['rx_bytes'] = 400000000
        data['interfaces'][0]['statistics']['tx_bytes'] = 100000000
        data['interfaces'][1]['statistics']['rx_bytes'] = 2000000000
        data['interfaces'][1]['statistics']['tx_bytes'] = 1000000000
        r = self._post_data(d.id, d.key, data, mock=False)
        self.assertEqual(r.status_code, 200)
        dd = DeviceData(pk=d.pk)
        self.assertDictEqual(dd.data, data)
        return dd

    def test_200_multiple_measurements(self):
        dd = self._create_multiple_measurements(mock=False)
        self.assertEqual(Metric.objects.count(), 6)
        self.assertEqual(Graph.objects.count(), 4)
        expected = {'wlan0': {'rx_bytes': 10000, 'tx_bytes': 6000},
                    'wlan1': {'rx_bytes': 4587, 'tx_bytes': 2993}}
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

    def test_garbage_clients(self):
        o = self._create_org()
        d = self._create_device(organization=o)
        r = self._post_data(d.id, d.key, self._garbage_clients, mock=False)
        # ignored
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Metric.objects.count(), 1)
        self.assertEqual(Graph.objects.count(), 1)

    @patch.object(monitoring_settings, 'AUTO_GRAPHS', return_value=[])
    def test_auto_graph_disabled(self, *args):
        self.assertEqual(Graph.objects.count(), 0)
        o = self._create_org()
        d = self._create_device(organization=o)
        self._post_data(d.id, d.key, self._data())
        self.assertEqual(Graph.objects.count(), 0)

    def test_get_device_metrics_200(self):
        r = Response(data=mock_data, status=200, content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.data['graphs'], list)
        self.assertEqual(len(r.data['graphs']), 4)
        self.assertIn('x', r.data)
        for graph in r.data['graphs']:
            self.assertIn('traces', graph)
            self.assertIn('description', graph)
            self.assertIn('type', graph)

    def test_get_device_metrics_histogram_ignore_x(self):
        r = Response(data=mock_histogram_data, status=200, content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(len(r.data['x']) > 50)

    def test_get_device_metrics_1d(self):
        r = Response(data=mock_data, status=200, content_type='application/json')
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

    # [WIP]
    # @patch('openwisp_monitoring.device.api.views.DeviceMetricView.get', side_effect=mock_get_csv)
    def test_get_device_metrics_csv(self):
        dd = self._create_single_measurement()
        d = self.device_model.objects.get(pk=dd.pk)
        r = self.client.get('{0}&csv=1'.format(self._url(d.pk, d.key)))
        self.assertEqual(r.get('Content-Disposition'), 'attachment; filename=data.csv')
        self.assertEqual(r.get('Content-Type'), 'text/csv')
        rows = r.content.decode('utf8').strip().split('\n')
        header = rows[0].strip().split(',')
        self.assertEqual(header, [
            'time',
            'download - wlan1 traffic (GB)',
            'upload - wlan1 traffic (GB)',
            'value',
            'download - wlan0 traffic (GB)',
            'upload - wlan0 traffic (GB)',
            'value'
        ])
        last_line = rows[-1].strip().split(',')
        self.assertEqual(last_line, [last_line[0], '2', '1', '2', '0.4', '0.1', '1'])

    def test_get_device_metrics_400_bad_timezone(self):
        dd = self._create_multiple_measurements()
        d = self.device_model.objects.get(pk=dd.pk)
        wrong_timezone_values = (
            'wrong',
            'America/Lima%27);%20DROP%20DATABASE%20test2;',
            'Europe/Cazzuoli'
        )
        for tz_value in wrong_timezone_values:
            url = '{0}&timezone={1}'.format(self._url(d.pk, d.key), tz_value)
            r = self.client.get(url)
            self.assertEqual(r.status_code, 400)
            self.assertIn('Unkown Time Zone', r.data)

    # testing admin here is more convenient because
    # we already have the code that creates test data

    def _login_admin(self):
        User = get_user_model()
        u = User.objects.create_superuser('admin', 'admin', 'test@test.com')
        self.client.force_login(u)

    def test_device_admin(self):
        dd = self._create_single_measurement()
        url = reverse('admin:config_device_change', args=[dd.pk])
        self._login_admin()
        r = self.client.get(url)
        self.assertContains(r, 'Device Status')
        self.assertContains(r, 'Monitoring Graph')
