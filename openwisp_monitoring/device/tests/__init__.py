import json
from copy import deepcopy

from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils.timezone import now
from swapper import load_model

from openwisp_controller.config.tests.utils import CreateConfigTemplateMixin

from ...monitoring.tests import TestMonitoringMixin
from ..utils import manage_short_retention_policy

Metric = load_model('monitoring', 'Metric')
DeviceData = load_model('device_monitoring', 'DeviceData')
WifiClient = load_model('device_monitoring', 'WifiClient')
WifiSession = load_model('device_monitoring', 'WifiSession')
Chart = load_model('monitoring', 'Chart')
Config = load_model('config', 'Config')
Device = load_model('config', 'Device')


class TestDeviceMonitoringMixin(CreateConfigTemplateMixin, TestMonitoringMixin):
    device_model = Device
    config_model = Config
    _PING = 'openwisp_monitoring.check.classes.Ping'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        manage_short_retention_policy()

    def _url(self, pk, key=None, time=None):
        url = reverse('monitoring:api_device_metric', args=[pk])
        if key:
            url = '{0}?key={1}'.format(url, key)
        if time:
            url = '{0}&time={1}'.format(url, time)
        return url

    def _post_data(self, id, key, data, time=None):
        if not time:
            time = now().utcnow().strftime('%d-%m-%Y_%H:%M:%S.%f')
        url = self._url(id, key, time)
        netjson = json.dumps(data)
        return self.client.post(url, netjson, content_type='application/json')

    def _create_device_monitoring(self):
        d = self._create_device(organization=self._create_org())
        dm = d.monitoring
        dm.status = 'ok'
        dm.save()
        return dm

    def _transform_wireless_interface_test_data(self, data):
        for interface in data.get('interfaces', []):
            wireless = interface.get('wireless')
            if wireless and all(key in wireless for key in ('htmode', 'clients')):
                for client in wireless['clients']:
                    htmode = wireless['htmode']
                    ht_enabled = htmode.startswith('HT')
                    vht_enabled = htmode.startswith('VHT')
                    noht_enabled = htmode == 'NOHT'
                    if noht_enabled:
                        client['ht'] = client['vht'] = None
                        # since 'he' field is optional
                        if 'he' in client:
                            client['he'] = None
                    elif ht_enabled:
                        if client['vht'] is False:
                            client['vht'] = None
                        if client.get('he') is False:
                            client['he'] = None
                    elif vht_enabled and client.get('he') is False:
                        client['he'] = None
            if wireless and 'bitrate' in wireless:
                wireless['bitrate'] = round(wireless['bitrate'] / 1000.0, 1)
        return data

    def assertDataDict(self, dd_data, data):
        """Compares monitoring data.

        This method is necessary because the wireless interface data is
        modified by the `AbstractDeviceData._transform_data` method.
        """
        data = self._transform_wireless_interface_test_data(data)
        self.assertDictEqual(dd_data, data)

    def create_test_data(self, no_resources=False, data=None, assertions=True):
        o = self._create_org()
        d = self._create_device(organization=o)
        if not data:
            data = self._data()
        # creation of resources metrics can be avoided in tests not involving them
        # this speeds up those tests by reducing requests made
        if no_resources:
            del data['resources']
        r = self._post_data(d.id, d.key, data)
        self.assertEqual(r.status_code, 200)
        dd = DeviceData(pk=d.pk)
        if not assertions:
            return dd
        self.assertDataDict(dd.data, data)
        if no_resources:
            metric_count, chart_count = 4, 4
        else:
            metric_count, chart_count = 7, 7
        # Exclude general metrics from the query
        self.assertEqual(Metric.objects.exclude(object_id=None).count(), metric_count)
        # Exclude general charts from the query
        self.assertEqual(
            Chart.objects.exclude(metric__object_id=None).count(), chart_count
        )
        if_dict = {'wlan0': data['interfaces'][0], 'wlan1': data['interfaces'][1]}
        extra_tags = {'organization_id': str(d.organization_id)}
        for ifname in ['wlan0', 'wlan1']:
            iface = if_dict[ifname]
            m = Metric.objects.get(
                key='traffic',
                field_name='rx_bytes',
                object_id=d.pk,
                main_tags={'ifname': ifname},
                extra_tags=extra_tags,
            )
            points = self._read_metric(
                m, limit=10, order='-time', extra_fields=['tx_bytes']
            )
            self.assertEqual(len(points), 1)
            for field in ['rx_bytes', 'tx_bytes']:
                self.assertEqual(points[0][field], iface['statistics'][field])
            m = Metric.objects.get(
                key='wifi_clients',
                field_name='clients',
                object_id=d.pk,
                extra_tags=extra_tags,
                main_tags={'ifname': ifname},
            )
            points = self._read_metric(m, limit=10, order='-time')
            self.assertEqual(len(points), len(iface['wireless']['clients']))
        return dd

    def _create_multiple_measurements(self, create=True, no_resources=False, count=4):
        if create:
            self.create_test_data(no_resources=no_resources)
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
        self.assertDataDict(dd.data, data4)
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
                    'type': 'wireless',
                    'up': True,
                    'mac': '44:d1:fa:4b:38:43',
                    'txqueuelen': 1000,
                    'multicast': True,
                    'mtu': 1500,
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
                        'htmode': 'HT20',
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
                                'he': False,
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
                    'type': 'wireless',
                    'up': True,
                    'mac': '44:d1:fa:4b:38:44',
                    'txqueuelen': 1000,
                    'multicast': True,
                    'mtu': 1500,
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
                        'bitrate': 1100,
                        'quality': 65,
                        'quality_max': 70,
                        'noise': -95,
                        'country': 'US',
                        'htmode': 'VHT80',
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

    mesh_interface = {
        "addresses": [
            {
                "address": "fe80::6670:2ff:fe3e:9e8b",
                "family": "ipv6",
                "mask": 64,
                "proto": "static",
            }
        ],
        "mac": "64:70:02:3e:9e:8b",
        "mtu": 1500,
        "multicast": True,
        "name": "mesh0-mng",
        "txqueuelen": 1000,
        "type": "wireless",
        "up": True,
        "wireless": {
            "channel": 11,
            "clients": [
                {
                    "auth": True,
                    "authorized": True,
                    "ht": True,
                    "mac": "A0:F3:C1:A5:FA:35",
                    "mfp": False,
                    "noise": -95,
                    "signal": 4,
                    "vht": False,
                    "wmm": True,
                }
            ],
            "country": "ES",
            "frequency": 2462,
            "htmode": "HT20",
            "mode": "802.11s",
            "noise": -95,
            "signal": 4,
            "ssid": "battlemesh-mng",
            "tx_power": 17,
        },
    }


class DeviceMonitoringTestCase(TestDeviceMonitoringMixin, TestCase):
    pass


class DeviceMonitoringTransactionTestcase(
    TestDeviceMonitoringMixin, TransactionTestCase
):
    pass


class TestWifiClientSessionMixin(TestDeviceMonitoringMixin):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        manage_short_retention_policy()

    @property
    def _sample_data(self):
        data = deepcopy(self._data())
        data.pop('resources')
        return data

    def _create_device_data(self, device=None):
        device = device or self._create_device()
        return DeviceData(pk=device.pk)

    def _save_device_data(self, device_data=None, data=None):
        dd = device_data or self._create_device_data()
        dd.data = data or self._sample_data
        dd.save_data()
        return dd

    def _create_wifi_client(self, **kwargs):
        options = {
            'mac_address': '22:33:44:55:66:77',
            'vendor': '',
            'ht': True,
            'vht': True,
            'wmm': False,
            'wds': False,
            'wps': False,
        }
        options.update(**kwargs)
        wifi_client = WifiClient(**options)
        wifi_client.full_clean()
        wifi_client.save()
        return wifi_client

    def _create_wifi_session(self, **kwargs):
        if 'wifi_client' not in kwargs:
            kwargs['wifi_client'] = self._create_wifi_client()
        if 'device' not in kwargs:
            kwargs['device'] = self._create_device()
        options = {'ssid': 'Free Public WiFi', 'interface_name': 'wlan0'}
        options.update(kwargs)
        wifi_session = WifiSession(**options)
        wifi_session.full_clean()
        wifi_session.save()
        return wifi_session
