import json
from copy import deepcopy

from django.test import TestCase
from django.urls import reverse
from swapper import load_model

from openwisp_controller.config.tests.utils import CreateConfigTemplateMixin

from ...monitoring.tests import TestMonitoringMixin
from ..utils import manage_short_retention_policy

Metric = load_model('monitoring', 'Metric')
DeviceData = load_model('device_monitoring', 'DeviceData')
Chart = load_model('monitoring', 'Chart')
Config = load_model('config', 'Config')
Device = load_model('config', 'Device')


class TestDeviceMonitoringMixin(CreateConfigTemplateMixin, TestMonitoringMixin):
    device_model = Device
    config_model = Config

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        manage_short_retention_policy()


class DeviceMonitoringTestCase(TestDeviceMonitoringMixin, TestCase):
    def _url(self, pk, key=None):
        url = reverse('monitoring:api_device_metric', args=[pk])
        if key:
            url = '{0}?key={1}'.format(url, key)
        return url

    def _post_data(self, id, key, data):
        url = self._url(id, key)
        netjson = json.dumps(data)
        return self.client.post(url, netjson, content_type='application/json')

    def create_test_adata(self, no_resources=False):
        o = self._create_org()
        d = self._create_device(organization=o)
        data = self._data()
        # creation of resources metrics can be avoided in tests not involving them
        # this speeds up those tests by reducing requests made
        if no_resources:
            del data['resources']
        r = self._post_data(d.id, d.key, data)
        self.assertEqual(r.status_code, 200)
        dd = DeviceData(pk=d.pk)
        self.assertDictEqual(dd.data, data)
        if no_resources:
            metric_count, chart_count = 4, 4
        else:
            metric_count, chart_count = 7, 7
        self.assertEqual(Metric.objects.count(), metric_count)
        self.assertEqual(Chart.objects.count(), chart_count)
        if_dict = {'wlan0': data['interfaces'][0], 'wlan1': data['interfaces'][1]}
        for ifname in ['wlan0', 'wlan1']:
            iface = if_dict[ifname]
            m = Metric.objects.get(key=ifname, field_name='rx_bytes', object_id=d.pk)
            points = m.read(limit=10, order='-time', extra_fields=['tx_bytes'])
            self.assertEqual(len(points), 1)
            for field in ['rx_bytes', 'tx_bytes']:
                self.assertEqual(points[0][field], iface['statistics'][field])
            m = Metric.objects.get(key=ifname, field_name='clients', object_id=d.pk)
            points = m.read(limit=10, order='-time')
            self.assertEqual(len(points), len(iface['wireless']['clients']))
        return dd

    def _create_multiple_measurements(self, create=True, no_resources=False, count=4):
        if create:
            self.create_test_adata(no_resources=no_resources)
        self.assertEqual(self.device_model.objects.count(), 1)
        d = self.device_model.objects.first()
        dd = DeviceData(pk=d.pk)
        data = self._data()
        # creation of resources metrics can be avoided in tests not involving them
        # this speeds up those tests by reducing requests made
        if no_resources:
            del data['resources']
        data2 = deepcopy(data)
        data2['interfaces'][0]['statistics']['rx_bytes'] = 400000000
        data2['interfaces'][0]['statistics']['tx_bytes'] = 100000000
        data2['interfaces'][1]['statistics']['rx_bytes'] = 2000000000
        data2['interfaces'][1]['statistics']['tx_bytes'] = 1000000000
        r = self._post_data(d.id, d.key, data2)
        if count == 2:
            return dd
        data3 = deepcopy(data)
        data3['interfaces'][0]['statistics']['rx_bytes'] = 500000000
        data3['interfaces'][0]['statistics']['tx_bytes'] = 300000000
        data3['interfaces'][1]['statistics']['rx_bytes'] = 0
        data3['interfaces'][1]['statistics']['tx_bytes'] = 0
        r = self._post_data(d.id, d.key, data3)
        if count == 3:
            return dd
        data4 = deepcopy(data)
        data4['interfaces'][0]['statistics']['rx_bytes'] = 1200000000
        data4['interfaces'][0]['statistics']['tx_bytes'] = 600000000
        data4['interfaces'][1]['statistics']['rx_bytes'] = 1000000000
        data4['interfaces'][1]['statistics']['tx_bytes'] = 500000000
        r = self._post_data(d.id, d.key, data4)
        self.assertEqual(r.status_code, 200)
        self.assertDictEqual(dd.data, data4)
        return dd

    def _data(self):
        return {
            'type': 'DeviceMonitoring',
            'general': {'local_time': 1589026500, 'uptime': 8003},
            'resources': {
                'cpus': 1,
                'memory': {
                    'total': 249774080,
                    'shared': 86016,
                    'free': 224497664,
                    'cached': 6774784,
                    'available': 223397664,
                    'buffered': 974848,
                },
                'load': [0, 0, 0],
                'disk': [
                    {
                        'used_bytes': 18792,
                        'available_bytes': 233984,
                        'filesystem': '/dev/root',
                        'mount_point': '/',
                        'used_percent': 7,
                        'size_bytes': 258016,
                    },
                    {
                        'used_bytes': 3872,
                        'available_bytes': 11916,
                        'filesystem': '/dev/sda1',
                        'mount_point': '/boot',
                        'used_percent': 25,
                        'size_bytes': 16112,
                    },
                ],
                'swap': {'free': 0, 'total': 0},
            },
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
                                'auth': True,
                                'signature': 'test_signature',
                            }
                        ],
                    },
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
                                'auth': True,
                                'signature': 'test_signature',
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
                                'auth': True,
                                'signature': 'test_signature',
                            },
                        ],
                    },
                },
            ],
        }
