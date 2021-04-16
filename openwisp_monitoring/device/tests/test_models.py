import json
from copy import deepcopy
from unittest.mock import patch

from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from swapper import load_model

from openwisp_controller.connection.tasks import update_config
from openwisp_controller.connection.tests.base import CreateConnectionsMixin
from openwisp_utils.tests import catch_signal

from ...db import timeseries_db
from ..signals import health_status_changed
from ..tasks import trigger_device_checks
from ..utils import get_device_cache_key
from . import DeviceMonitoringTestCase

DeviceMonitoring = load_model('device_monitoring', 'DeviceMonitoring')
DeviceData = load_model('device_monitoring', 'DeviceData')


class BaseTestCase(DeviceMonitoringTestCase):
    _sample_data = {
        "type": "DeviceMonitoring",
        "general": {
            "hostname": "10-BA-00-FF-E1-9B",
            "local_time": 1519645078,
            "uptime": 1519645078,
        },
        "resources": {
            "load": [10144, 15456, 6624],
            "memory": {
                "buffered": 3334144,
                'cached': 6774784,
                "free": 79429632,
                "shared": 102400,
                "total": 128430080,
            },
            'disk': [
                {
                    'used_bytes': 18792,
                    'available_bytes': 233984,
                    'filesystem': '/dev/root',
                    'mount_point': '/',
                    'used_percent': 7,
                    'size_bytes': 258016,
                }
            ],
            "swap": {"free": 0, "total": 0},
        },
        "interfaces": [
            {
                "name": "wlan0",
                "statistics": {
                    "collisions": 0,
                    "multicast": 0,
                    "rx_bytes": 0,
                    "rx_compressed": 0,
                    "rx_crc_errors": 0,
                    "rx_dropped": 0,
                    "rx_errors": 0,
                    "rx_fifo_errors": 0,
                    "rx_frame_errors": 0,
                    "rx_length_errors": 0,
                    "rx_missed_errors": 0,
                    "rx_over_errors": 0,
                    "rx_packets": 0,
                    "tx_aborted_errors": 0,
                    "tx_bytes": 864,
                    "tx_carrier_errors": 0,
                    "tx_compressed": 0,
                    "tx_dropped": 0,
                    "tx_errors": 0,
                    "tx_fifo_errors": 0,
                    "tx_heartbeat_errors": 0,
                    "tx_packets": 7,
                    "tx_window_errors": 0,
                },
                "wireless": {
                    "channel": 1,
                    "country": "US",
                    "mode": "access_point",
                    "tx_power": 6,
                    "frequency": 5180,
                    "mode": "access_point",
                    "noise": -103,
                    "signal": -56,
                    "ssid": "wifi-test",
                    "clients": [
                        {
                            "aid": 1,
                            "assoc": True,
                            "auth": True,
                            "authorized": True,
                            "ht": True,
                            "mac": "44:D1:FA:4B:00:00",
                            "mfp": False,
                            "preauth": False,
                            "rrm": [0, 0, 0, 0, 0],
                            "signature": "test_signature",
                            "vht": True,
                            "wds": False,
                            "wmm": True,
                            "wps": False,
                        }
                    ],
                },
            },
            {
                "name": "wlan1",
                "statistics": {
                    "collisions": 0,
                    "multicast": 0,
                    "rx_bytes": 0,
                    "rx_compressed": 0,
                    "rx_crc_errors": 0,
                    "rx_dropped": 0,
                    "rx_errors": 0,
                    "rx_fifo_errors": 0,
                    "rx_frame_errors": 0,
                    "rx_length_errors": 0,
                    "rx_missed_errors": 0,
                    "rx_over_errors": 0,
                    "rx_packets": 0,
                    "tx_aborted_errors": 0,
                    "tx_bytes": 136840,
                    "tx_carrier_errors": 0,
                    "tx_compressed": 0,
                    "tx_dropped": 0,
                    "tx_errors": 0,
                    "tx_fifo_errors": 0,
                    "tx_heartbeat_errors": 0,
                    "tx_packets": 293,
                    "tx_window_errors": 0,
                },
                "wireless": {
                    "channel": 1,
                    "country": "US",
                    "frequency": 2412,
                    "mode": "access_point",
                    "noise": -95,
                    "ssid": "testnet",
                    "tx_power": 6,
                    "signal": -56,
                    "clients": [
                        {
                            "aid": 1,
                            "assoc": True,
                            "auth": True,
                            "authorized": True,
                            "ht": True,
                            "mac": "44:D1:FA:4B:00:01",
                            "mfp": False,
                            "preauth": False,
                            "rrm": [0, 0, 0, 0, 0],
                            "signature": "test_signature",
                            "vht": True,
                            "wds": False,
                            "wmm": True,
                            "wps": False,
                        }
                    ],
                },
                "addresses": [
                    {
                        "proto": "static",
                        "family": "ipv4",
                        "address": "192.168.1.1",
                        "mask": 8,
                    },
                    {
                        "proto": "dhcp",
                        "family": "ipv4",
                        "address": "10.0.0.4",
                        "mask": 24,
                    },
                    {
                        "proto": "static",
                        "family": "ipv6",
                        "address": "2001:3238:dfe1:ec63::fefb",
                        "mask": 12,
                    },
                    {
                        "proto": "dhcp",
                        "family": "ipv6",
                        "address": "fd46:9038:f983::1",
                        "mask": 22,
                    },
                ],
            },
        ],
        "dhcp_leases": [
            {
                "expiry": 1586943200,
                "mac": "f2:f1:3e:56:d2:77",
                "ip": "192.168.66.196",
                "client_name": "MyPhone1",
                "client_id": "01:20:f4:78:19:3b:38",
            },
            {
                "expiry": 1586943200,
                "mac": "f2:f1:3e:56:d2:77",
                "ip": "fe80::9683:c4ff:fe02:c2bf",
                "client_name": "MyPhone1",
                "client_id": "01:20:f4:78:19:3b:38",
            },
        ],
        "neighbors": [
            {
                "ip": "fe80::9683:c4ff:fe02:c2bf",
                "mac": "44:D1:FA:4B:00:02",
                "interface": "eth2",
                "state": "REACHABLE",
            },
            {
                "ip": "192.168.56.1",
                "mac": "44:D1:FA:4B:00:03",
                "interface": "br-mng",
                "state": "STALE",
            },
            {
                "ip": "192.168.56.2",
                "mac": "44:D1:FA:4B:00:04",
                "interface": "br-mng",
                "state": "STALE",
            },
        ],
    }

    def _create_device(self, **kwargs):
        if 'organization' not in kwargs:
            kwargs['organization'] = self._create_org()
        return super()._create_device(**kwargs)

    def _create_device_data(self, **kwargs):
        d = self._create_device(**kwargs)
        return DeviceData(pk=d.pk)


class TestDeviceData(BaseTestCase):
    """
    Test openwisp_monitoring.device.models.DeviceData
    """

    def test_clean_data_ok(self):
        dd = self._create_device_data()
        dd.data = {'type': 'DeviceMonitoring', 'interfaces': []}
        dd.validate_data()

    def test_clean_sample_data_ok(self):
        dd = self._create_device_data()
        dd.data = self._sample_data
        dd.validate_data()

    def test_clean_data_fail(self):
        dd = self._create_device_data()
        try:
            dd.data = {'type': 'DeviceMonitoring', 'interfaces': [{}]}
            dd.validate_data()
        except ValidationError as e:
            self.assertIn('Invalid data in', e.message)
            self.assertIn('"#/interfaces/0"', e.message)
        else:
            self.fail('ValidationError not raised')

    def test_validate_neighbors_data(self):
        dd = self._create_device_data()
        try:
            dd.data = deepcopy(self._sample_data)
            dd.data["neighbors"][0]["ip"] = "invalid"
            dd.validate_data()
        except ValidationError as e:
            self.assertIn('Invalid data in', e.message)
            self.assertIn("is not a 'ipv4'", e.message)
        else:
            self.fail('ValidationError not raised')

    def test_save_data(self):
        dd = self._create_device_data()
        dd.data = deepcopy(self._sample_data)
        dd.save_data()
        return dd

    def test_read_data(self):
        dd = self.test_save_data()
        dd = DeviceData(pk=dd.pk)
        self.assertEqual(dd.data, self._sample_data)

    def test_read_data_none(self):
        dd = self._create_device_data()
        self.assertEqual(dd.data, None)

    def test_json(self):
        dd = self._create_device_data()
        dd.data = self._sample_data
        try:
            json.loads(dd.json(indent=True))
        except Exception:
            self.fail('json method did not return valid JSON')

    def test_init(self):
        dd = DeviceData()
        self.assertIsNone(dd.data)
        dd = DeviceData(data=self._sample_data)
        self.assertEqual(dd.data, self._sample_data)

    def test_device_deleted(self):
        d = self._create_device()
        metric = self._create_object_metric(name='test', content_object=d)
        metric.full_clean()
        metric.save()
        d.delete()
        try:
            metric.refresh_from_db()
        except ObjectDoesNotExist:
            pass
        else:
            self.fail('metric was not deleted')

    def test_device_data_time_stamp(self):
        dd = self.test_save_data()
        dd = DeviceData(pk=dd.pk)
        dd.data
        self.assertIsNotNone(dd.data_timestamp)

    def test_local_time_update(self):
        dd = deepcopy(self.test_save_data())
        dd = DeviceData(pk=dd.pk)
        data = dd.data_user_friendly
        self.assertNotEqual(
            data['general']['local_time'], self._sample_data['general']['local_time']
        )

    def test_uptime_update(self):
        dd = deepcopy(self.test_save_data())
        dd = DeviceData(pk=dd.pk)
        data = dd.data_user_friendly
        self.assertNotEqual(
            data['general']['uptime'], self._sample_data['general']['uptime']
        )

    def test_bad_address_fail(self):
        dd = self._create_device_data()
        data = deepcopy(self._sample_data)
        data['interfaces'][1]['addresses'][0]['address'] = '123'
        try:
            dd.data = data
            dd.validate_data()
        except ValidationError as e:
            self.assertIn('Invalid data in', e.message)
            self.assertIn("'123\' is not a \'ipv4\'", e.message)
        else:
            self.fail('ValidationError not raised')

    def test_bad_dhcp_lease_fail(self):
        dd = self._create_device_data()
        data = deepcopy(self._sample_data)
        data['dhcp_leases'][0]['ip'] = '123'
        try:
            dd.data = data
            dd.validate_data()
        except ValidationError as e:
            self.assertIn('Invalid data in', e.message)
            self.assertIn("'123\' is not a \'ipv4\'", e.message)
        else:
            self.fail('ValidationError not raised')

    def test_cached_memory_optional(self):
        dd = self._create_device_data()
        data = deepcopy(self._sample_data)
        del data['resources']['memory']['cached']
        dd.data = data
        dd.validate_data()

    @patch('openwisp_monitoring.device.settings.MAC_VENDOR_DETECTION', True)
    def test_mac_vendor_info(self):
        dd = self.test_save_data()
        dd = DeviceData(pk=dd.pk)
        vendor = 'Shenzhen Yunlink Technology Co., Ltd'
        assert dd.data['interfaces']
        assert dd.data['neighbors']
        assert dd.data['dhcp_leases']
        for interface in dd.data['interfaces']:
            if 'wireless' not in interface and 'clients' not in interface['wireless']:
                continue
            for client in interface['wireless']['clients']:
                self.assertIn('vendor', client)
                self.assertEqual(client['vendor'], vendor)
        for neighbor in dd.data['neighbors']:
            self.assertIn('vendor', neighbor)
            self.assertEqual(neighbor['vendor'], vendor)
        for lease in dd.data['dhcp_leases']:
            self.assertIn('vendor', lease)

    @patch('openwisp_monitoring.device.settings.MAC_VENDOR_DETECTION', True)
    def test_mac_vendor_info_empty(self):
        dd = self._create_device_data()
        dd.data = deepcopy(self._sample_data)
        dd.data['neighbors'] = [
            {'ip': '2001:db80::1', 'interface': 'eth2.1', 'state': 'FAILED'}
        ]
        dd.save_data()
        self.assertEqual(dd.data['neighbors'][0]['vendor'], '')

    def test_bad_disk_fail(self):
        dd = self._create_device_data()
        data = deepcopy(self._sample_data)
        with self.subTest('Incorrect type'):
            data['resources']['disk'] = dict()
            try:
                dd.data = data
                dd.validate_data()
            except ValidationError as e:
                self.assertIn('Invalid data in', e.message)
                self.assertIn("{} is not of type \'array\'", e.message)
            else:
                self.fail('ValidationError not raised')
        with self.subTest('Missing required fields'):
            data['resources']['disk'] = [{'used_bytes': 18792}]
            try:
                dd.data = data
                dd.validate_data()
            except ValidationError as e:
                self.assertIn('Invalid data in', e.message)
                self.assertIn("'mount_point\' is a required property", e.message)
            else:
                self.fail('ValidationError not raised')
        with self.subTest('Incorrect field type'):
            data = deepcopy(self._sample_data)
            data['resources']['disk'][0]['used_bytes'] = 18792.12
            try:
                dd.data = data
                dd.validate_data()
            except ValidationError as e:
                self.assertIn('Invalid data in', e.message)
                self.assertIn("18792.12 is not of type \'integer\'", e.message)
            else:
                self.fail('ValidationError not raised')

    def test_resources_no_key(self):
        dd = self._create_device_data()
        with self.subTest('Test No Resources'):
            data = deepcopy(self._sample_data)
            del data['resources']
            dd.data = data
            dd.validate_data()
        with self.subTest('Test No Load'):
            data = deepcopy(self._sample_data)
            del data['resources']['load']
            dd.data = data
            dd.validate_data()
        with self.subTest('Test No Memory'):
            data = deepcopy(self._sample_data)
            del data['resources']['memory']
            dd.data = data
            dd.validate_data()
        with self.subTest('Test No Disk'):
            data = deepcopy(self._sample_data)
            del data['resources']['disk']
            dd.data = data
            dd.validate_data()

    @patch('logging.Logger.warning')
    def test_trigger_device_checks_task_resiliency(self, mock):
        dd = DeviceData(name='Test Device')
        trigger_device_checks.delay(dd.pk)
        mock.assert_called_with(f'The device with uuid {dd.pk} has been deleted')

    def test_device_data_cache_set(self):
        dd = self.create_test_data(no_resources=True)
        cache_key = get_device_cache_key(dd, context='current-data')
        cache_data = cache.get(cache_key)[0]['data']
        self.assertEqual(json.loads(cache_data), dd.data)
        with patch.object(timeseries_db, 'query', side_effect=Exception):
            dd.refresh_from_db()
            self.assertEqual(json.loads(cache_data), dd.data)

    @patch('openwisp_controller.connection.tasks.logger.info')
    def test_can_be_updated(self, mocked_logger_info):
        device = self._create_device_config()
        device.monitoring.status = 'critical'
        device.monitoring.save()
        update_config.delay(device.pk)
        mocked_logger_info.assert_called_once()

    @patch('openwisp_controller.connection.tasks.logger.info')
    def test_can_be_updated_unknown(self, mocked_logger_info):
        device = self._create_device_config()
        device.monitoring.status = 'unknown'
        device.monitoring.save()
        update_config.delay(device.pk)
        mocked_logger_info.assert_called_once()


class TestDeviceMonitoring(CreateConnectionsMixin, BaseTestCase):
    """
    Test openwisp_monitoring.device.models.DeviceMonitoring
    """

    def _create_env(self):
        d = self._create_device()
        dm = d.monitoring
        dm.status = 'ok'
        dm.save()
        ping = self._create_object_metric(
            name='ping', key='ping', field_name='reachable', content_object=d
        )
        self._create_alert_settings(
            metric=ping, custom_operator='<', custom_threshold=1, custom_tolerance=0
        )
        load = self._create_object_metric(name='load', content_object=d)
        self._create_alert_settings(
            metric=load, custom_operator='>', custom_threshold=90, custom_tolerance=0
        )
        process_count = self._create_object_metric(
            name='process_count', content_object=d
        )
        self._create_alert_settings(
            metric=process_count,
            custom_operator='>',
            custom_threshold=20,
            custom_tolerance=0,
        )
        return dm, ping, load, process_count

    def test_status_changed(self):
        dm, ping, load, process_count = self._create_env()
        # check signal
        with catch_signal(health_status_changed) as handler:
            dm.update_status('problem')
        dm.refresh_from_db()
        self.assertEqual(dm.status, 'problem')
        handler.assert_called_once_with(
            instance=dm,
            status='problem',
            sender=DeviceMonitoring,
            signal=health_status_changed,
        )

    def test_ok_critical_ok(self):
        dm, ping, load, process_count = self._create_env()
        self.assertEqual(dm.status, 'ok')
        ping.check_threshold(0)
        self.assertEqual(dm.status, 'critical')
        ping.check_threshold(1)
        self.assertEqual(dm.status, 'ok')

    def test_ok_problem_ok(self):
        dm, ping, load, process_count = self._create_env()
        self.assertEqual(dm.status, 'ok')
        load.check_threshold(100)
        self.assertEqual(dm.status, 'problem')
        load.check_threshold(20)
        self.assertEqual(dm.status, 'ok')

    def test_ok_problem_critical_problem_ok(self):
        dm, ping, load, process_count = self._create_env()
        self.assertEqual(dm.status, 'ok')
        load.check_threshold(100)
        self.assertEqual(dm.status, 'problem')
        ping.check_threshold(0)
        self.assertEqual(dm.status, 'critical')
        ping.check_threshold(1)
        self.assertEqual(dm.status, 'problem')
        load.check_threshold(80)
        self.assertEqual(dm.status, 'ok')

    def test_ok_critical_critical_critical_ok(self):
        dm, ping, load, process_count = self._create_env()
        self.assertEqual(dm.status, 'ok')
        ping.check_threshold(0)
        self.assertEqual(dm.status, 'critical')
        load.check_threshold(100)
        self.assertEqual(dm.status, 'critical')
        load.check_threshold(80)
        self.assertEqual(dm.status, 'critical')
        ping.check_threshold(1)
        self.assertEqual(dm.status, 'ok')

    def test_ok_problem_problem_problem_ok(self):
        dm, ping, load, process_count = self._create_env()
        self.assertEqual(dm.status, 'ok')
        load.check_threshold(100)
        self.assertEqual(dm.status, 'problem')
        process_count.check_threshold(40)
        self.assertEqual(dm.status, 'problem')
        process_count.check_threshold(10)
        self.assertEqual(dm.status, 'problem')
        load.check_threshold(80)
        self.assertEqual(dm.status, 'ok')

    def test_management_ip_clear_device_offline(self):
        dm, ping, load, process_count = self._create_env()
        dm.device.management_ip = '10.10.0.5'
        dm.device.save()
        self.assertEqual(dm.status, 'ok')
        self.assertEqual(dm.device.management_ip, '10.10.0.5')
        ping.check_threshold(0)
        self.assertEqual(dm.status, 'critical')
        self.assertIsNone(dm.device.management_ip)

    @patch('openwisp_monitoring.device.settings.AUTO_CLEAR_MANAGEMENT_IP', False)
    def test_management_ip_not_clear_device_online(self):
        dm, ping, load, process_count = self._create_env()
        dm.device.management_ip = '10.10.0.5'
        dm.device.save()
        self.assertEqual(dm.status, 'ok')
        self.assertEqual(dm.device.management_ip, '10.10.0.5')
        ping.check_threshold(0)
        self.assertEqual(dm.status, 'critical')
        self.assertIsNotNone(dm.device.management_ip)

    def _set_env_unknown(self, load, process_count, ping, dm):
        dm.status = 'unknown'
        dm.save()
        ping.is_healthy = None
        load.save()
        load.is_healthy = None
        ping.save()
        process_count.is_healthy = None
        process_count.save()

    def test_unknown_ok(self):
        dm, ping, load, process_count = self._create_env()
        self._set_env_unknown(load, process_count, ping, dm)
        load.delete()
        process_count.delete()
        dm.refresh_from_db()
        self.assertEqual(dm.status, 'unknown')
        ping.write(1)
        dm.refresh_from_db()
        self.assertEqual(dm.status, 'ok')

    def test_unknown_critical(self):
        dm, ping, load, process_count = self._create_env()
        self._set_env_unknown(load, process_count, ping, dm)
        load.delete()
        process_count.delete()
        dm.refresh_from_db()
        self.assertEqual(dm.status, 'unknown')
        ping.write(0)
        dm.refresh_from_db()
        self.assertEqual(dm.status, 'critical')
