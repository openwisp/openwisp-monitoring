import json
from copy import deepcopy
from unittest import skipIf
from unittest.mock import patch

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from swapper import is_swapped, load_model

from openwisp_controller.connection.models import Credentials, DeviceConnection
from openwisp_utils.tests import catch_signal

from ....monitoring.utils import get_db
from ... import settings as app_settings
from ...models import DeviceData
from ...signals import health_status_changed
from ...tests import DeviceMonitoringTestCase
from ...utils import SHORT_RP

Check = load_model('check', 'Check')


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
                "free": 79429632,
                "shared": 102400,
                "total": 128430080,
            },
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
                        },
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
                        },
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
        "neighbors": [
            {
                "ip_address": "fe80::9683:c4ff:fe02:c2bf",
                "mac_address": "44:D1:FA:4B:00:02",
                "interface": "eth2",
                "state": "REACHABLE",
            },
            {
                "ip_address": "192.168.56.1",
                "mac_address": "44:D1:FA:4B:00:03",
                "interface": "br-mng",
                "state": "STALE",
            },
            {
                "ip_address": "192.168.56.2",
                "mac_address": "44:D1:FA:4B:00:04",
                "interface": "br-mng",
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


class BaseTestDeviceData(object):
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
            dd.data["neighbors"][0]["ip_address"] = "invalid"
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
        dd = self.data_model(pk=dd.pk)
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
        dd = self.data_model()
        self.assertIsNone(dd.data)
        dd = self.data_model(data=self._sample_data)
        self.assertEqual(dd.data, self._sample_data)

    def test_retention_policy(self):
        rp = get_db().get_list_retention_policies()
        self.assertEqual(len(rp), 2)
        self.assertEqual(rp[1]['name'], SHORT_RP)
        self.assertEqual(rp[1]['default'], False)
        duration = app_settings.SHORT_RETENTION_POLICY
        self.assertEqual(rp[1]['duration'], duration)

    def test_device_deleted(self):
        d = self._create_device()
        metric = self._create_object_metric(name='test', content_object=d,)
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
        dd = self.data_model(pk=dd.pk)
        dd.data
        self.assertIsNotNone(dd.data_timestamp)

    def test_local_time_update(self):
        dd = deepcopy(self.test_save_data())
        dd = self.data_model(pk=dd.pk)
        data = dd.data_user_friendly
        self.assertNotEqual(
            data['general']['local_time'], self._sample_data['general']['local_time']
        )

    def test_uptime_update(self):
        dd = deepcopy(self.test_save_data())
        dd = self.data_model(pk=dd.pk)
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

    @patch('openwisp_monitoring.device.settings.MAC_VENDOR_DETECTION', True)
    def test_mac_vendor_info(self):
        dd = self.test_save_data()
        dd = self.data_model(pk=dd.pk)
        vendor = 'Shenzhen Yunlink Technology Co., Ltd'
        for interface in dd.data['interfaces']:
            if 'wireless' not in interface and 'clients' not in interface['wireless']:
                continue
            for client in interface['wireless']['clients']:
                self.assertIn('vendor', client)
                self.assertEqual(client['vendor'], vendor)
        for neighbor in dd.data['neighbors']:
            self.assertIn('vendor', neighbor)
            self.assertEqual(neighbor['vendor'], vendor)


class BaseTestDeviceMonitoring(object):
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
        self._create_threshold(metric=ping, operator='<', value=1, seconds=0)
        load = self._create_object_metric(name='load', content_object=d)
        self._create_threshold(metric=load, operator='>', value=90, seconds=0)
        process_count = self._create_object_metric(
            name='process_count', content_object=d
        )
        self._create_threshold(metric=process_count, operator='>', value=20, seconds=0)
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
            sender=load_model(self.app_name, self.model_name),
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
        self.assertEqual(dm.status, 'ok')

    def test_unknown_critical(self):
        dm, ping, load, process_count = self._create_env()
        self._set_env_unknown(load, process_count, ping, dm)
        load.delete()
        process_count.delete()
        dm.refresh_from_db()
        self.assertEqual(dm.status, 'unknown')
        ping.write(0)
        self.assertEqual(dm.status, 'critical')

    def test_unknown_problem_ok(self):
        dm, ping, load, process_count = self._create_env()
        self._set_env_unknown(load, process_count, ping, dm)
        dm.refresh_from_db()
        self.assertEqual(dm.status, 'unknown')
        load.check_threshold(100)
        self.assertEqual(dm.status, 'problem')
        load.check_threshold(20)
        self.assertEqual(dm.status, 'ok')

    def test_device_connection_change(self):
        admin = self._create_admin()
        Notification = load_model('notifications', 'Notification')
        d = self._create_device()
        dm = d.monitoring
        dm.status = 'unknown'
        dm.save()
        c = Credentials.objects.create()
        dc = DeviceConnection.objects.create(credentials=c, device=d)
        dc.is_working = True
        dc.save()
        self.assertEqual(dm.status, 'ok')
        n = Notification.objects.get(level='info')
        self.assertEqual(n.verb, 'connected successfully')
        self.assertEqual(n.actor, d)
        dc.is_working = False
        dc.save()
        n = Notification.objects.get(level='warning')
        self.assertEqual(n.verb, 'not working')
        self.assertEqual(n.actor, d)
        self.assertEqual(n.recipient, admin)

    @skipIf(is_swapped('check', 'Check'), 'Running tests on sample_app')
    @patch('openwisp_monitoring.check.models.Check.perform_check')
    def test_is_working_false_true(self, mocked_call):
        d = self._create_device()
        dm = d.monitoring
        dm.status = 'unknown'
        dm.save()
        ping_path = 'openwisp_monitoring.check.classes.Ping'
        Check.objects.create(name='Check', content_object=d, check=ping_path)
        c = Credentials.objects.create()
        dc = DeviceConnection.objects.create(credentials=c, device=d)
        dc.is_working = True
        dc.save()
        mocked_call.assert_called_once()

    @skipIf(is_swapped('check', 'Check'), 'Running tests on sample_app')
    @patch('openwisp_monitoring.check.models.Check.perform_check')
    def test_is_working_true_false(self, mocked_call):
        d = self._create_device()
        dm = d.monitoring
        dm.status = 'ok'
        dm.save()
        ping_path = 'openwisp_monitoring.check.classes.Ping'
        Check.objects.create(name='Check', content_object=d, check=ping_path)
        c = Credentials.objects.create()
        dc = DeviceConnection.objects.create(credentials=c, device=d)
        dc.is_working = False
        dc.save()
        mocked_call.assert_called_once()
