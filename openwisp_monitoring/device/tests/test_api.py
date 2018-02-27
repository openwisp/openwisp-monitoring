import json

from django.test import TestCase
from django.urls import reverse

from openwisp_controller.config.models import Config, Device
from openwisp_controller.config.tests import CreateConfigTemplateMixin

from ...monitoring.models import Graph, Metric
from ...monitoring.tests import TestMonitoringMixin
from ..models import DeviceData


class TestDeviceApi(CreateConfigTemplateMixin, TestMonitoringMixin, TestCase):
    """
    Tests API (device metric collection)
    """
    device_model = Device
    config_model = Config

    def _url(self, pk, key=None):
        url = reverse('monitoring:api_device_metric', args=[pk])
        if key:
            url = '{0}?key={1}'.format(url, key)
        return url

    def _post_data(self, id, key, data):
        url = self._url(id, key)
        netjson = json.dumps(data)
        return self.client.post(url, netjson, content_type='application/json')

    def _data(self):
        return {
            'type': 'DeviceMonitoring',
            'interfaces': [
                {
                    'name': 'wlan0',
                    'statistics': {
                        'rx_bytes': 324,
                        'tx_bytes': 145
                    },
                    'clients': {
                        '00:ee:ad:34:f5:3b': {
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
                    }
                },
                {
                    'name': 'wlan1',
                    'statistics': {
                        'rx_bytes': 826,
                        'tx_bytes': 2275
                    },
                    'clients': {
                        '11:dd:ce:53:d1:5a': {
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
                        '12:d3:be:63:d1:5a': {
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
                    }
                }
            ]
        }

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

    def test_405(self):
        o = self._create_org()
        d = self._create_device(organization=o)
        r = self.client.get(self._url(d.pk, d.key),
                            content_type='application/json')
        self.assertEqual(r.status_code, 405)

    def test_400(self):
        o = self._create_org()
        d = self._create_device(organization=o)
        r = self._post_data(d.id, d.key, {'interfaces': []})
        self.assertEqual(r.status_code, 400)
        r = self._post_data(d.id, d.key, {'type': 'wrong'})
        self.assertEqual(r.status_code, 400)
        r = self._post_data(d.id, d.key, {
            'type': 'DeviceMonitoring', 'interfaces': [{}]
        })
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
        if_dict = {'wlan0': data['interfaces'][0],
                   'wlan1': data['interfaces'][1]}
        for ifname in ['wlan0', 'wlan1']:
            iface = if_dict[ifname]
            for field_name in ['rx_bytes', 'tx_bytes']:
                m = Metric.objects.get(key=ifname, field_name=field_name,
                                       object_id=d.pk)
                points = m.read(limit=10, order='time DESC')
                self.assertEqual(len(points), 1)
                self.assertEqual(points[0][m.field_name],
                                 iface['statistics'][field_name])
            m = Metric.objects.get(key=ifname, field_name='clients',
                                   object_id=d.pk)
            points = m.read(limit=10, order='time DESC')
            self.assertEqual(len(points), len(iface['clients'].keys()))

    def test_200_traffic_counter_incremented(self):
        self.test_200_create()
        self.assertEqual(Device.objects.count(), 1)
        d = Device.objects.first()
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
            self.assertEqual(len(points), len(iface['clients'].keys()) * 2)

    def test_200_traffic_counter_reset(self):
        self.test_200_create()
        self.assertEqual(Device.objects.count(), 1)
        d = Device.objects.first()
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
            self.assertEqual(len(points), len(iface['clients'].keys()) * 2)

    def test_200_multiple_measurements(self):
        self.test_200_create()
        self.assertEqual(Device.objects.count(), 1)
        d = Device.objects.first()
        data2 = self._data()
        data2['interfaces'][0]['statistics']['rx_bytes'] = 100000000
        data2['interfaces'][0]['statistics']['tx_bytes'] = 400000000
        data2['interfaces'][1]['statistics']['rx_bytes'] = 1000000000
        data2['interfaces'][1]['statistics']['tx_bytes'] = 2000000000
        r = self._post_data(d.id, d.key, data2)
        data3 = self._data()
        data3['interfaces'][0]['statistics']['rx_bytes'] = 300000000
        data3['interfaces'][0]['statistics']['tx_bytes'] = 500000000
        data3['interfaces'][1]['statistics']['rx_bytes'] = 0
        data3['interfaces'][1]['statistics']['tx_bytes'] = 0
        r = self._post_data(d.id, d.key, data3)
        data4 = self._data()
        data4['interfaces'][0]['statistics']['rx_bytes'] = 600000000
        data4['interfaces'][0]['statistics']['tx_bytes'] = 1200000000
        data4['interfaces'][1]['statistics']['rx_bytes'] = 500000000
        data4['interfaces'][1]['statistics']['tx_bytes'] = 1000000000
        r = self._post_data(d.id, d.key, data4)
        self.assertEqual(r.status_code, 200)
        dd = DeviceData(pk=d.pk)
        self.assertDictEqual(dd.data, data4)
        self.assertEqual(Metric.objects.count(), 6)
        self.assertEqual(Graph.objects.count(), 4)
        expected = {'wlan0': {'rx_bytes': 6000, 'tx_bytes': 10000},
                    'wlan1': {'rx_bytes': 2993, 'tx_bytes': 4587}}
        # wlan0 rx_bytes
        m = Metric.objects.get(key='wlan0', field_name='rx_bytes', object_id=d.pk)
        points = m.read(limit=10, order='time DESC')
        self.assertEqual(len(points), 4)
        expected = [300000000, 200000000, 99999676, 324]
        for i, point in enumerate(points):
            self.assertEqual(point['rx_bytes'], expected[i])
        # wlan0 tx_bytes
        m = Metric.objects.get(key='wlan0', field_name='tx_bytes', object_id=d.pk)
        points = m.read(limit=10, order='time DESC')
        self.assertEqual(len(points), 4)
        expected = [700000000, 100000000, 399999855, 145]
        for i, point in enumerate(points):
            self.assertEqual(point['tx_bytes'], expected[i])
        g = m.graph_set.first()
        data = g.read()
        # expected download wlan0
        self.assertEqual(data['graphs'][0][1][-1], 1.2)
        # expected upload wlan0
        self.assertEqual(data['graphs'][1][1][-1], 0.6)
        # wlan1 rx_bytes
        m = Metric.objects.get(key='wlan1', field_name='rx_bytes', object_id=d.pk)
        points = m.read(limit=10, order='time DESC')
        self.assertEqual(len(points), 4)
        expected = [500000000, 0, 999999174, 826]
        for i, point in enumerate(points):
            self.assertEqual(point['rx_bytes'], expected[i])
        # wlan1 tx_bytes
        m = Metric.objects.get(key='wlan1', field_name='tx_bytes', object_id=d.pk)
        points = m.read(limit=10, order='time DESC')
        self.assertEqual(len(points), 4)
        expected = [1000000000, 0, 1999997725, 2275]
        for i, point in enumerate(points):
            self.assertEqual(point['tx_bytes'], expected[i])
        g = m.graph_set.first()
        data = g.read()
        # expected download wlan1
        self.assertEqual(data['graphs'][0][1][-1], 3.0)
        # expected upload wlan1
        self.assertEqual(data['graphs'][1][1][-1], 1.5)
