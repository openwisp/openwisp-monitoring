import json

from django.test import TestCase
from django.urls import reverse

from openwisp_controller.config.models import Config, Device
from openwisp_controller.config.tests import CreateConfigTemplateMixin

from ...monitoring.tests import TestMonitoringMixin
from ..utils import manage_short_retention_policy


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
