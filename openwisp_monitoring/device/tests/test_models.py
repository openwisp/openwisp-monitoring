import json

from django.core.exceptions import ValidationError

from ...monitoring.utils import get_db
from ...tests import catch_signal
from .. import settings as app_settings
from ..models import DeviceData, DeviceMonitoring
from ..signals import health_status_changed
from ..utils import SHORT_RP
from . import DeviceMonitoringTestCase


class BaseTestCase(DeviceMonitoringTestCase):
    _sample_data = {
        "type": "DeviceMonitoring",
        "general": {
            "hostname": "10-BA-00-FF-E1-9B",
            "local_time": 1519645078,
            "uptime": 1519645078
        },
        "resources": {
            "load": [
                10144,
                15456,
                6624
            ],
            "memory": {
                "buffered": 3334144,
                "free": 79429632,
                "shared": 102400,
                "total": 128430080
            },
            "swap": {
                "free": 0,
                "total": 0
            }
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
                    "tx_window_errors": 0
                },
                "wireless": {
                    "channel": 1,
                    "clients": {},
                    "country": "US",
                    "tx_power": 6
                }
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
                    "tx_window_errors": 0
                },
                "wireless": {
                    "channel": 1,
                    "clients": {},
                    "country": "US",
                    "frequency": 2412,
                    "mode": "access_point",
                    "noise": -95,
                    "ssid": "testnet",
                    "tx_power": 6
                }
            }
        ]
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

    def test_save_data(self):
        dd = self._create_device_data()
        dd.data = self._sample_data
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

    def test_retention_policy(self):
        rp = get_db().get_list_retention_policies()
        self.assertEqual(len(rp), 2)
        self.assertEqual(rp[1]['name'], SHORT_RP)
        self.assertEqual(rp[1]['default'], False)
        duration = app_settings.SHORT_RETENTION_POLICY
        self.assertEqual(rp[1]['duration'], duration)


class TestDeviceMonitoring(BaseTestCase):
    """
    Test openwisp_monitoring.device.models.DeviceMonitoring
    """
    def _create_env(self):
        d = self._create_device()
        dm = d.monitoring
        ping = self._create_object_metric(name='ping',
                                          key='ping',
                                          field_name='reachable',
                                          content_object=d)
        self._create_threshold(metric=ping,
                               operator='<',
                               value=1,
                               seconds=0)
        load = self._create_object_metric(name='load',
                                          content_object=d)
        self._create_threshold(metric=load,
                               operator='>',
                               value=90,
                               seconds=0)
        process_count = self._create_object_metric(name='process_count',
                                                   content_object=d)
        self._create_threshold(metric=process_count,
                               operator='>',
                               value=20,
                               seconds=0)
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
