from json import loads
from unittest.mock import call, patch

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TransactionTestCase
from swapper import load_model

from openwisp_controller.connection.connectors.ssh import Ssh
from openwisp_controller.connection.models import DeviceConnection
from openwisp_controller.connection.settings import CONNECTORS, UPDATE_STRATEGIES
from openwisp_controller.connection.tests.utils import CreateConnectionsMixin, SshServer
from openwisp_monitoring.check.classes.iperf3 import get_iperf3_schema
from openwisp_monitoring.check.classes.iperf3 import logger as iperf3_logger

from ...device.tests import TestDeviceMonitoringMixin
from .. import settings as app_settings
from ..classes import Iperf3
from .iperf3_test_utils import (
    INVALID_PARAMS,
    PARAM_ERROR,
    RESULT_AUTH_FAIL,
    RESULT_FAIL,
    RESULT_TCP,
    RESULT_UDP,
    TEST_RSA_KEY,
)

Check = load_model('check', 'Check')
Chart = load_model('monitoring', 'Chart')
Metric = load_model('monitoring', 'Metric')
AlertSettings = load_model('monitoring', 'AlertSettings')


class TestIperf3(
    CreateConnectionsMixin, TestDeviceMonitoringMixin, TransactionTestCase
):
    _IPERF3 = app_settings.CHECK_CLASSES[2][0]
    _RESULT_KEYS = [
        'iperf3_result',
        'sent_bps_tcp',
        'received_bps_tcp',
        'sent_bytes_tcp',
        'received_bytes_tcp',
        'retransmits',
        'sent_bps_udp',
        'sent_bytes_udp',
        'jitter',
        'total_packets',
        'lost_packets',
        'lost_percent',
    ]
    _IPERF3_TEST_SERVER = ['iperf3.openwisptestserver.com']
    _IPERF3_TEST_MULTIPLE_SERVERS = [
        'iperf3.openwisptestserver1.com',
        'iperf3.openwisptestserver2.com',
    ]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mock_ssh_server = SshServer(
            {'root': cls._TEST_RSA_PRIVATE_KEY_PATH}
        ).__enter__()
        cls.ssh_server.port = cls.mock_ssh_server.port

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.mock_ssh_server.__exit__()
        app_settings.IPERF3_CHECK_CONFIG = {}

    def setUp(self):
        ckey = self._create_credentials_with_key(port=self.ssh_server.port)
        self.dc = self._create_device_connection(credentials=ckey)
        self.device = self.dc.device
        self.org_id = str(self.device.organization.id)
        self.dc.connect()
        app_settings.IPERF3_CHECK_CONFIG = {
            self.org_id: {'host': self._IPERF3_TEST_SERVER}
        }
        self._EXPECTED_COMMAND_CALLS = [
            call(
                (
                    'iperf3 -c iperf3.openwisptestserver.com -p 5201 -t 10 --connect-timeout 1000 '
                    '-b 0 -l 128K -w 0 -P 1  -J'
                ),
                raise_unexpected_exit=False,
            ),
            call(
                (
                    'iperf3 -c iperf3.openwisptestserver.com -p 5201 -t 10 --connect-timeout 1000 '
                    '-b 30M -l 0 -w 0 -P 1  -u -J'
                ),
                raise_unexpected_exit=False,
            ),
        ]
        self._EXPECTED_WARN_CALLS = [
            call(
                (
                    f'Iperf3 check failed for "{self.device}", '
                    'error - unable to connect to server: Connection refused'
                )
            ),
            call(
                (
                    f'Iperf3 check failed for "{self.device}", '
                    'error - unable to connect to server: Connection refused'
                )
            ),
        ]

    def _perform_iperf3_check(self, object_id=None):
        if not object_id:
            object_id = self.device.id
        check = Check.objects.get(check_type=self._IPERF3, object_id=object_id)
        return check.perform_check(store=False)

    def _set_auth_expected_calls(self, config):
        password = config[self.org_id]['password']
        username = config[self.org_id]['username']
        server = 'iperf3.openwisptestserver.com'
        test_prefix = '-----BEGIN PUBLIC KEY-----\n'
        test_suffix = '\n-----END PUBLIC KEY-----'
        key = config[self.org_id]['rsa_public_key']
        rsa_key_path = '/tmp/iperf3-public-key.pem'

        self._EXPECTED_COMMAND_CALLS = [
            call(
                (
                    f'echo "{test_prefix}{key}{test_suffix}" > {rsa_key_path} && '
                    f'IPERF3_PASSWORD="{password}" iperf3 -c {server} -p 5201 -t 10 '
                    f'--username "{username}" --rsa-public-key-path {rsa_key_path} --connect-timeout 1000 '
                    f'-b 0 -l 128K -w 0 -P 1  -J'
                ),
                raise_unexpected_exit=False,
            ),
            call(
                (
                    f'IPERF3_PASSWORD="{password}" iperf3 -c {server} -p 5201 -t 10 '
                    f'--username "{username}" --rsa-public-key-path {rsa_key_path} --connect-timeout 1000 '
                    f'-b 30M -l 0 -w 0 -P 1  -u -J '
                    f'&& rm -f {rsa_key_path}'
                ),
                raise_unexpected_exit=False,
            ),
        ]

    def _assert_iperf3_fail_result(self, result):
        for key in self._RESULT_KEYS:
            self.assertIn(key, result)
        self.assertEqual(result['iperf3_result'], 0)
        self.assertEqual(result['sent_bps_tcp'], 0.0)
        self.assertEqual(result['received_bps_tcp'], 0.0)
        self.assertEqual(result['sent_bytes_tcp'], 0)
        self.assertEqual(result['received_bytes_tcp'], 0)
        self.assertEqual(result['retransmits'], 0)
        self.assertEqual(result['sent_bps_udp'], 0.0)
        self.assertEqual(result['sent_bytes_udp'], 0)
        self.assertEqual(result['jitter'], 0.0)
        self.assertEqual(result['total_packets'], 0)
        self.assertEqual(result['lost_percent'], 0.0)

    @patch.object(Ssh, 'exec_command')
    @patch.object(iperf3_logger, 'warning')
    def test_iperf3_check_no_params(self, mock_warn, mock_exec_command):
        mock_exec_command.side_effect = [(RESULT_TCP, 0), (RESULT_UDP, 0)]
        # By default check params {}
        tcp_result = loads(RESULT_TCP)['end']
        udp_result = loads(RESULT_UDP)['end']['sum']
        result = self._perform_iperf3_check()
        for key in self._RESULT_KEYS:
            self.assertIn(key, result)
        self.assertEqual(result['iperf3_result'], 1)
        self.assertEqual(
            result['sent_bps_tcp'], tcp_result['sum_sent']['bits_per_second']
        )
        self.assertEqual(
            result['received_bytes_tcp'], tcp_result['sum_received']['bytes']
        )
        self.assertEqual(result['jitter'], udp_result['jitter_ms'])
        self.assertEqual(result['total_packets'], udp_result['packets'])
        self.assertEqual(mock_warn.call_count, 0)
        self.assertEqual(mock_exec_command.call_count, 2)
        mock_exec_command.assert_has_calls(self._EXPECTED_COMMAND_CALLS)

    @patch.object(Ssh, 'exec_command')
    @patch.object(iperf3_logger, 'warning')
    def test_iperf3_check_params(self, mock_warn, mock_exec_command):
        mock_exec_command.side_effect = [(RESULT_TCP, 0), (RESULT_UDP, 0)]
        check = Check.objects.get(check_type=self._IPERF3)
        tcp_result = loads(RESULT_TCP)['end']
        udp_result = loads(RESULT_UDP)['end']['sum']
        server = self._IPERF3_TEST_SERVER[0]
        test_prefix = '-----BEGIN PUBLIC KEY-----\n'
        test_suffix = '\n-----END PUBLIC KEY-----'
        rsa_key_path = '/tmp/test-rsa.pem'
        test_params = {
            'username': 'openwisp-test-user',
            'password': 'openwisp_pass',
            'rsa_public_key': TEST_RSA_KEY,
            'client_options': {
                'port': 6201,
                'time': 20,
                'window': '300K',
                'parallel': 5,
                'reverse': True,
                'connect_timeout': 1000,
                'tcp': {'bitrate': '10M', 'length': '128K'},
                'udp': {'bitrate': '50M', 'length': '400K'},
            },
        }
        time = test_params['client_options']['time']
        port = test_params['client_options']['port']
        window = test_params['client_options']['window']
        parallel = test_params['client_options']['parallel']
        tcp_bitrate = test_params['client_options']['tcp']['bitrate']
        tcp_len = test_params['client_options']['tcp']['length']
        udp_bitrate = test_params['client_options']['udp']['bitrate']
        udp_len = test_params['client_options']['udp']['length']
        username = test_params['username']
        password = test_params['password']
        key = test_params['rsa_public_key']
        rsa_key_path = '/tmp/iperf3-public-key.pem'
        check.params = test_params
        check.save()
        self._EXPECTED_COMMAND_CALLS = [
            call(
                (
                    f'echo "{test_prefix}{key}{test_suffix}" > {rsa_key_path} && '
                    f'IPERF3_PASSWORD="{password}" iperf3 -c {server} -p {port} -t {time} '
                    f'--username "{username}" --rsa-public-key-path {rsa_key_path} --connect-timeout 1000 '
                    f'-b {tcp_bitrate} -l {tcp_len} -w {window} -P {parallel} --reverse -J'
                ),
                raise_unexpected_exit=False,
            ),
            call(
                (
                    f'IPERF3_PASSWORD="{password}" iperf3 -c {server} -p {port} -t {time} '
                    f'--username "{username}" --rsa-public-key-path {rsa_key_path} --connect-timeout 1000 '
                    f'-b {udp_bitrate} -l {udp_len} -w {window} -P {parallel} --reverse -u -J '
                    f'&& rm -f {rsa_key_path}'
                ),
                raise_unexpected_exit=False,
            ),
        ]
        result = self._perform_iperf3_check()
        for key in self._RESULT_KEYS:
            self.assertIn(key, result)
        self.assertEqual(result['iperf3_result'], 1)
        self.assertEqual(
            result['sent_bps_tcp'], tcp_result['sum_sent']['bits_per_second']
        )
        self.assertEqual(
            result['received_bytes_tcp'], tcp_result['sum_received']['bytes']
        )
        self.assertEqual(result['jitter'], udp_result['jitter_ms'])
        self.assertEqual(result['total_packets'], udp_result['packets'])
        self.assertEqual(mock_warn.call_count, 0)
        self.assertEqual(mock_exec_command.call_count, 2)
        mock_exec_command.assert_has_calls(self._EXPECTED_COMMAND_CALLS)

    @patch.object(Ssh, 'exec_command')
    @patch.object(iperf3_logger, 'warning')
    def test_iperf3_check_config(self, mock_warn, mock_exec_command):
        mock_exec_command.side_effect = [(RESULT_TCP, 0), (RESULT_UDP, 0)]
        tcp_result = loads(RESULT_TCP)['end']
        udp_result = loads(RESULT_UDP)['end']['sum']
        self._EXPECTED_COMMAND_CALLS = [
            call(
                (
                    'iperf3 -c iperf3.openwisptestserver.com -p 9201 -k 1M --connect-timeout 2000 '
                    '-b 10M -l 512K -w 0 -P 1 --bidir -J'
                ),
                raise_unexpected_exit=False,
            ),
            call(
                (
                    'iperf3 -c iperf3.openwisptestserver.com -p 9201 -k 1M --connect-timeout 2000 '
                    '-b 50M -l 256K -w 0 -P 1 --bidir -u -J'
                ),
                raise_unexpected_exit=False,
            ),
        ]
        iperf3_config = {
            self.org_id: {
                'host': ['iperf3.openwisptestserver.com'],
                'client_options': {
                    'port': 9201,
                    'time': 120,
                    'connect_timeout': 2000,
                    'bytes': '20M',
                    'blockcount': '1M',
                    'bidirectional': True,
                    'tcp': {'bitrate': '10M', 'length': '512K'},
                    'udp': {'bitrate': '50M', 'length': '256K'},
                },
            }
        }
        with patch.object(app_settings, 'IPERF3_CHECK_CONFIG', iperf3_config):
            with patch.object(Iperf3, 'schema', get_iperf3_schema()):
                result = self._perform_iperf3_check()
                for key in self._RESULT_KEYS:
                    self.assertIn(key, result)
                self.assertEqual(result['iperf3_result'], 1)
                self.assertEqual(
                    result['sent_bps_tcp'], tcp_result['sum_sent']['bits_per_second']
                )
                self.assertEqual(
                    result['received_bytes_tcp'], tcp_result['sum_received']['bytes']
                )
                self.assertEqual(result['jitter'], udp_result['jitter_ms'])
                self.assertEqual(result['total_packets'], udp_result['packets'])
                self.assertEqual(mock_warn.call_count, 0)
                self.assertEqual(mock_exec_command.call_count, 2)
                mock_exec_command.assert_has_calls(self._EXPECTED_COMMAND_CALLS)

    @patch.object(iperf3_logger, 'warning')
    def test_iperf3_device_connection(self, mock_warn):
        dc = self.dc

        with self.subTest(
            'Test iperf3 check active device connection when the management tunnel is down'
        ):
            with patch.object(
                DeviceConnection, 'connect', return_value=False
            ) as mocked_connect:
                self._perform_iperf3_check()
                mock_warn.assert_called_once_with(
                    f'Failed to get a working DeviceConnection for "{self.device}", iperf3 check skipped!'
                )
            self.assertEqual(mocked_connect.call_count, 1)
        mock_warn.reset_mock()

        with self.subTest('Test iperf3 check when device connection is not enabled'):
            dc.enabled = False
            dc.save()
            self._perform_iperf3_check()
            mock_warn.assert_called_once_with(
                f'Failed to get a working DeviceConnection for "{self.device}", iperf3 check skipped!'
            )
        mock_warn.reset_mock()

        with self.subTest(
            'Test iperf3 check with different credential connector type ie. snmp'
        ):
            device2 = self._create_device(
                name='test-device-2', mac_address='00:11:22:33:44:66'
            )
            params = {'community': 'public', 'agent': 'snmp-agent', 'port': 161}
            snmp_credentials = self._create_credentials(
                params=params, connector=CONNECTORS[1][0], auto_add=True
            )
            dc2 = self._create_device_connection(
                device=device2,
                credentials=snmp_credentials,
                update_strategy=UPDATE_STRATEGIES[0][0],
            )
            dc2.is_working = True
            dc2.enabled = True
            dc2.save()
            self._perform_iperf3_check(object_id=device2.id)
            mock_warn.assert_called_once_with(
                f'Failed to get a working DeviceConnection for "{device2}", iperf3 check skipped!'
            )

    @patch.object(iperf3_logger, 'info')
    def test_iperf3_check_device_monitoring_critical(self, mock_info):
        self.device.monitoring.update_status('critical')
        self._perform_iperf3_check()
        mock_info.assert_called_once_with(
            (
                f'"{self.device}" DeviceMonitoring '
                'health status is "critical", iperf3 check skipped!'
            )
        )

    def test_iperf3_check_content_object_none(self):
        check = Check(name='Iperf3 check', check_type=self._IPERF3, params={})
        try:
            check.check_instance.validate()
        except ValidationError as e:
            self.assertIn('device', str(e))
        else:
            self.fail('ValidationError not raised')

    def test_iperf3_check_content_object_not_device(self):
        check = Check(
            name='Iperf3 check',
            check_type=self._IPERF3,
            content_object=self._create_user(),
            params={},
        )
        try:
            check.check_instance.validate()
        except ValidationError as e:
            self.assertIn('device', str(e))
        else:
            self.fail('ValidationError not raised')

    def test_iperf3_check_schema_violation(self):
        for invalid_param in INVALID_PARAMS:
            check = Check(
                name='Iperf3 check',
                check_type=self._IPERF3,
                content_object=self.device,
                params=invalid_param,
            )
            try:
                check.check_instance.validate()
            except ValidationError as e:
                self.assertIn('Invalid param', str(e))
            else:
                self.fail('ValidationError not raised')

    @patch.object(Ssh, 'exec_command')
    @patch.object(iperf3_logger, 'warning')
    def test_iperf3_check(self, mock_warn, mock_exec_command):
        error = "ash: iperf3: not found"
        tcp_result = loads(RESULT_TCP)['end']
        udp_result = loads(RESULT_UDP)['end']['sum']
        iperf3_json_error_config = {
            self.org_id: {
                'host': ['iperf3.openwisptestserver.com'],
                'username': 'test',
                'password': 'testpass',
                'rsa_public_key': 'INVALID_RSA_KEY',
            }
        }
        with patch.object(
            app_settings, 'IPERF3_CHECK_CONFIG', iperf3_json_error_config
        ):
            with self.subTest('Test iperf3 errors not in json format'):
                mock_exec_command.side_effect = [(PARAM_ERROR, 1), (PARAM_ERROR, 1)]
                EXPECTED_WARN_CALLS = [
                    call(
                        f'Iperf3 check failed for "{self.device}", error - {PARAM_ERROR}'
                    ),
                    call(
                        f'Iperf3 check failed for "{self.device}", error - {PARAM_ERROR}'
                    ),
                ]
                self._perform_iperf3_check()
                self.assertEqual(mock_warn.call_count, 2)
                self.assertEqual(mock_exec_command.call_count, 2)
                mock_warn.assert_has_calls(EXPECTED_WARN_CALLS)
            mock_warn.reset_mock()
            mock_exec_command.reset_mock()

        with self.subTest('Test iperf3 is not installed on the device'):
            mock_exec_command.side_effect = [(error, 127)]
            self._perform_iperf3_check()
            mock_warn.assert_called_with(
                f'Iperf3 is not installed on the "{self.device}", error - {error}'
            )
            self.assertEqual(mock_warn.call_count, 1)
            self.assertEqual(mock_exec_command.call_count, 1)
        mock_warn.reset_mock()
        mock_exec_command.reset_mock()

        with self.subTest('Test iperf3 check passes in both TCP & UDP'):
            mock_exec_command.side_effect = [(RESULT_TCP, 0), (RESULT_UDP, 0)]
            self.assertEqual(Chart.objects.count(), 2)
            self.assertEqual(Metric.objects.count(), 2)
            result = self._perform_iperf3_check()
            for key in self._RESULT_KEYS:
                self.assertIn(key, result)
            self.assertEqual(result['iperf3_result'], 1)
            self.assertEqual(
                result['sent_bps_tcp'], tcp_result['sum_sent']['bits_per_second']
            )
            self.assertEqual(
                result['received_bps_tcp'],
                tcp_result['sum_received']['bits_per_second'],
            )
            self.assertEqual(result['sent_bytes_tcp'], tcp_result['sum_sent']['bytes'])
            self.assertEqual(
                result['received_bytes_tcp'], tcp_result['sum_received']['bytes']
            )
            self.assertEqual(
                result['retransmits'], tcp_result['sum_sent']['retransmits']
            )
            self.assertEqual(result['sent_bps_udp'], udp_result['bits_per_second'])
            self.assertEqual(result['sent_bytes_udp'], udp_result['bytes'])
            self.assertEqual(result['jitter'], udp_result['jitter_ms'])
            self.assertEqual(result['total_packets'], udp_result['packets'])
            self.assertEqual(result['lost_percent'], udp_result['lost_percent'])
            self.assertEqual(Chart.objects.count(), 8)
            self.assertEqual(Check.objects.count(), 3)
            iperf3_metric = Metric.objects.get(key='iperf3')
            self.assertEqual(Metric.objects.count(), 3)
            self.assertEqual(iperf3_metric.content_object, self.device)
            points = self._read_metric(
                iperf3_metric, limit=None, extra_fields=list(result.keys())
            )
            self.assertEqual(len(points), 1)
            self.assertEqual(points[0]['iperf3_result'], result['iperf3_result'])
            self.assertEqual(points[0]['sent_bps_tcp'], result['sent_bps_tcp'])
            self.assertEqual(
                points[0]['received_bytes_tcp'], result['received_bytes_tcp']
            )
            self.assertEqual(points[0]['retransmits'], result['retransmits'])
            self.assertEqual(points[0]['sent_bps_udp'], result['sent_bps_udp'])
            self.assertEqual(points[0]['sent_bytes_udp'], result['sent_bytes_udp'])
            self.assertEqual(points[0]['jitter'], result['jitter'])
            self.assertEqual(points[0]['total_packets'], result['total_packets'])
            self.assertEqual(points[0]['lost_packets'], result['lost_packets'])
            self.assertEqual(points[0]['lost_percent'], result['lost_percent'])
            self.assertEqual(mock_warn.call_count, 0)
            self.assertEqual(mock_exec_command.call_count, 2)
            mock_exec_command.assert_has_calls(self._EXPECTED_COMMAND_CALLS)
        mock_warn.reset_mock()
        mock_exec_command.reset_mock()

        with self.subTest('Test iperf3 check fails in both TCP & UDP'):
            mock_exec_command.side_effect = [(RESULT_FAIL, 1), (RESULT_FAIL, 1)]
            result = self._perform_iperf3_check()
            self._assert_iperf3_fail_result(result)
            self.assertEqual(Chart.objects.count(), 8)
            self.assertEqual(Metric.objects.count(), 3)
            self.assertEqual(mock_warn.call_count, 2)
            self.assertEqual(mock_exec_command.call_count, 2)
            mock_warn.assert_has_calls(self._EXPECTED_WARN_CALLS)
            mock_exec_command.assert_has_calls(self._EXPECTED_COMMAND_CALLS)
        mock_warn.reset_mock()
        mock_exec_command.reset_mock()

        with self.subTest('Test iperf3 check TCP pass UDP fail'):
            mock_exec_command.side_effect = [(RESULT_TCP, 0), (RESULT_FAIL, 1)]
            result = self._perform_iperf3_check()
            for key in self._RESULT_KEYS:
                self.assertIn(key, result)
            self.assertEqual(result['iperf3_result'], 1)
            self.assertEqual(
                result['sent_bps_tcp'], tcp_result['sum_sent']['bits_per_second']
            )
            self.assertEqual(
                result['received_bps_tcp'],
                tcp_result['sum_received']['bits_per_second'],
            )
            self.assertEqual(result['sent_bytes_tcp'], tcp_result['sum_sent']['bytes'])
            self.assertEqual(
                result['received_bytes_tcp'], tcp_result['sum_received']['bytes']
            )
            self.assertEqual(
                result['retransmits'], tcp_result['sum_sent']['retransmits']
            )
            self.assertEqual(result['sent_bps_udp'], 0.0)
            self.assertEqual(result['sent_bytes_udp'], 0)
            self.assertEqual(result['jitter'], 0.0)
            self.assertEqual(result['total_packets'], 0)
            self.assertEqual(result['lost_percent'], 0.0)
            self.assertEqual(Chart.objects.count(), 8)
            self.assertEqual(Metric.objects.count(), 3)
            self.assertEqual(mock_warn.call_count, 1)
            self.assertEqual(mock_exec_command.call_count, 2)
            mock_warn.assert_has_calls(self._EXPECTED_WARN_CALLS[1:])
            mock_exec_command.assert_has_calls(self._EXPECTED_COMMAND_CALLS)
        mock_warn.reset_mock()
        mock_exec_command.reset_mock()

        with self.subTest('Test iperf3 check TCP fail UDP pass'):
            mock_exec_command.side_effect = [(RESULT_FAIL, 1), (RESULT_UDP, 0)]
            result = self._perform_iperf3_check()
            for key in self._RESULT_KEYS:
                self.assertIn(key, result)
            self.assertEqual(result['iperf3_result'], 1)
            self.assertEqual(result['sent_bps_tcp'], 0.0)
            self.assertEqual(result['received_bps_tcp'], 0.0)
            self.assertEqual(result['sent_bytes_tcp'], 0)
            self.assertEqual(result['received_bytes_tcp'], 0)
            self.assertEqual(result['retransmits'], 0)
            self.assertEqual(result['sent_bps_udp'], udp_result['bits_per_second'])
            self.assertEqual(result['sent_bytes_udp'], udp_result['bytes'])
            self.assertEqual(result['jitter'], udp_result['jitter_ms'])
            self.assertEqual(result['total_packets'], udp_result['packets'])
            self.assertEqual(result['lost_percent'], udp_result['lost_percent'])
            self.assertEqual(Chart.objects.count(), 8)
            self.assertEqual(Metric.objects.count(), 3)
            self.assertEqual(mock_warn.call_count, 1)
            self.assertEqual(mock_exec_command.call_count, 2)
            mock_warn.assert_has_calls(self._EXPECTED_WARN_CALLS[1:])
            mock_exec_command.assert_has_calls(self._EXPECTED_COMMAND_CALLS)

    @patch.object(Ssh, 'exec_command')
    @patch.object(iperf3_logger, 'warning')
    def test_iperf3_check_auth_config(self, mock_warn, mock_exec_command):
        iperf3_config = {
            self.org_id: {
                'host': self._IPERF3_TEST_SERVER,
                'username': 'test',
                'password': 'testpass',
                'rsa_public_key': TEST_RSA_KEY,
            }
        }
        iperf3_conf_wrong_pass = {
            self.org_id: {
                'host': self._IPERF3_TEST_SERVER,
                'username': 'test',
                'password': 'wrongpass',
                'rsa_public_key': TEST_RSA_KEY,
            }
        }
        iperf3_conf_wrong_user = {
            self.org_id: {
                'host': self._IPERF3_TEST_SERVER,
                'username': 'wronguser',
                'password': 'testpass',
                'rsa_public_key': TEST_RSA_KEY,
            }
        }
        auth_error = "test authorization failed"
        tcp_result = loads(RESULT_TCP)['end']
        udp_result = loads(RESULT_UDP)['end']['sum']

        self._EXPECTED_WARN_CALLS = [
            call(f'Iperf3 check failed for "{self.device}", error - {auth_error}'),
            call(f'Iperf3 check failed for "{self.device}", error - {auth_error}'),
        ]
        with self.subTest('Test iperf3 check with right config'):
            with patch.object(
                app_settings,
                'IPERF3_CHECK_CONFIG',
                iperf3_config,
                # It is required to mock "Iperf3.schema" here so that it
                # uses the updated configuration from "IPERF3_CHECK_CONFIG" setting.
            ), patch.object(Iperf3, 'schema', get_iperf3_schema()):
                self._set_auth_expected_calls(iperf3_config)
                mock_exec_command.side_effect = [(RESULT_TCP, 0), (RESULT_UDP, 0)]
                result = self._perform_iperf3_check()
                for key in self._RESULT_KEYS:
                    self.assertIn(key, result)
                self.assertEqual(result['iperf3_result'], 1)
                self.assertEqual(
                    result['sent_bps_tcp'], tcp_result['sum_sent']['bits_per_second']
                )
                self.assertEqual(
                    result['received_bytes_tcp'], tcp_result['sum_received']['bytes']
                )
                self.assertEqual(result['jitter'], udp_result['jitter_ms'])
                self.assertEqual(result['total_packets'], udp_result['packets'])
                self.assertEqual(mock_warn.call_count, 0)
                self.assertEqual(mock_exec_command.call_count, 2)
                mock_exec_command.assert_has_calls(self._EXPECTED_COMMAND_CALLS)
            mock_warn.reset_mock()
            mock_exec_command.reset_mock()

        with self.subTest('Test iperf3 check with wrong password'):
            with patch.object(
                app_settings, 'IPERF3_CHECK_CONFIG', iperf3_conf_wrong_pass
            ), patch.object(Iperf3, 'schema', get_iperf3_schema()):
                self._set_auth_expected_calls(iperf3_conf_wrong_pass)
                mock_exec_command.side_effect = [
                    (RESULT_AUTH_FAIL, 1),
                    (RESULT_AUTH_FAIL, 1),
                ]

                result = self._perform_iperf3_check()
                self._assert_iperf3_fail_result(result)
                self.assertEqual(mock_warn.call_count, 2)
                self.assertEqual(mock_exec_command.call_count, 2)
                mock_warn.assert_has_calls(self._EXPECTED_WARN_CALLS)
                mock_exec_command.assert_has_calls(self._EXPECTED_COMMAND_CALLS)
            mock_warn.reset_mock()
            mock_exec_command.reset_mock()

        with self.subTest('Test iperf3 check with wrong username'):
            with patch.object(
                app_settings, 'IPERF3_CHECK_CONFIG', iperf3_conf_wrong_user
            ), patch.object(Iperf3, 'schema', get_iperf3_schema()):
                self._set_auth_expected_calls(iperf3_conf_wrong_user)
                mock_exec_command.side_effect = [
                    (RESULT_AUTH_FAIL, 1),
                    (RESULT_AUTH_FAIL, 1),
                ]

                result = self._perform_iperf3_check()
                self._assert_iperf3_fail_result(result)
                self.assertEqual(mock_warn.call_count, 2)
                self.assertEqual(mock_exec_command.call_count, 2)
                mock_warn.assert_has_calls(self._EXPECTED_WARN_CALLS)
                mock_exec_command.assert_has_calls(self._EXPECTED_COMMAND_CALLS)

    @patch.object(Ssh, 'exec_command')
    @patch.object(iperf3_logger, 'warning')
    @patch.object(iperf3_logger, 'info')
    @patch.object(cache, 'add')
    def test_iperf3_check_task_with_multiple_server_config(self, *args):
        mock_add = args[0]
        mock_info = args[1]
        mock_warn = args[2]
        mock_exec_command = args[3]
        org = self.device.organization
        iperf3_multiple_server_config = {
            self.org_id: {'host': self._IPERF3_TEST_MULTIPLE_SERVERS}
        }
        check = Check.objects.get(check_type=self._IPERF3)

        self._EXPECTED_COMMAND_CALLS_SERVER_1 = [
            call(
                (
                    f'iperf3 -c {self._IPERF3_TEST_MULTIPLE_SERVERS[0]} -p 5201 -t 10 --connect-timeout 1000 '
                    '-b 0 -l 128K -w 0 -P 1  -J'
                ),
                raise_unexpected_exit=False,
            ),
            call(
                (
                    f'iperf3 -c {self._IPERF3_TEST_MULTIPLE_SERVERS[0]} -p 5201 -t 10 --connect-timeout 1000 '
                    '-b 30M -l 0 -w 0 -P 1  -u -J'
                ),
                raise_unexpected_exit=False,
            ),
        ]
        self._EXPECTED_COMMAND_CALLS_SERVER_2 = [
            call(
                (
                    f'iperf3 -c {self._IPERF3_TEST_MULTIPLE_SERVERS[1]} -p 5201 -t 10 --connect-timeout 1000 '
                    '-b 0 -l 128K -w 0 -P 1  -J'
                ),
                raise_unexpected_exit=False,
            ),
            call(
                (
                    f'iperf3 -c {self._IPERF3_TEST_MULTIPLE_SERVERS[1]} -p 5201 -t 10 --connect-timeout 1000 '
                    '-b 30M -l 0 -w 0 -P 1  -u -J'
                ),
                raise_unexpected_exit=False,
            ),
        ]

        with patch.object(app_settings, 'IPERF3_CHECK_CONFIG', {}):
            with self.subTest('Test iperf3 check without config'):
                self._perform_iperf3_check()
                mock_warn.assert_called_with(
                    (
                        f'Iperf3 servers for organization "{org}" '
                        f'is not configured properly, iperf3 check skipped!'
                    )
                )
                self.assertEqual(mock_warn.call_count, 1)
            mock_warn.reset_mock()

        with patch.object(
            app_settings,
            'IPERF3_CHECK_CONFIG',
            {'invalid_org_uuid': {'host': self._IPERF3_TEST_SERVER, 'time': 10}},
        ):
            with self.subTest('Test iperf3 check with invalid config'):
                self._perform_iperf3_check()
                mock_warn.assert_called_with(
                    (
                        f'Iperf3 servers for organization "{org}" '
                        f'is not configured properly, iperf3 check skipped!'
                    )
                )
                self.assertEqual(mock_warn.call_count, 1)
            mock_warn.reset_mock()

        with patch.object(
            app_settings, 'IPERF3_CHECK_CONFIG', iperf3_multiple_server_config
        ):
            with self.subTest(
                'Test iperf3 check when all iperf3 servers are available'
            ):
                mock_add.return_value = True
                mock_exec_command.side_effect = [(RESULT_TCP, 0), (RESULT_UDP, 0)]
                self._perform_iperf3_check()
                self.assertEqual(mock_warn.call_count, 0)
                self.assertEqual(mock_add.call_count, 1)
                self.assertEqual(mock_exec_command.call_count, 2)
                mock_exec_command.assert_has_calls(
                    self._EXPECTED_COMMAND_CALLS_SERVER_1
                )
            mock_add.reset_mock()
            mock_warn.reset_mock()
            mock_exec_command.reset_mock()

            with self.subTest(
                'Test iperf3 check when single iperf3 server are available'
            ):
                mock_add.side_effect = [False, True]
                mock_exec_command.side_effect = [(RESULT_TCP, 0), (RESULT_UDP, 0)]
                self._perform_iperf3_check()
                self.assertEqual(mock_warn.call_count, 0)
                self.assertEqual(mock_add.call_count, 2)
                self.assertEqual(mock_exec_command.call_count, 2)
                mock_exec_command.assert_has_calls(
                    self._EXPECTED_COMMAND_CALLS_SERVER_2
                )
            mock_add.reset_mock()
            mock_warn.reset_mock()
            mock_exec_command.reset_mock()

            with self.subTest(
                'Test iperf3 check when all iperf3 servers are occupied initially'
            ):
                # If all available iperf3 servers are occupied initially,
                # then push the task back in the queue and acquire the iperf3
                # server only after completion of previous running checks
                mock_add.side_effect = [False, False, True]
                mock_exec_command.side_effect = [(RESULT_TCP, 0), (RESULT_UDP, 0)]
                self._perform_iperf3_check()
                mock_info.has_called_with(
                    (
                        f'At the moment, all available iperf3 servers of organization "{org}" '
                        f'are busy running checks, putting "{check}" back in the queue..'
                    )
                )
                self.assertEqual(mock_info.call_count, 4)
                self.assertEqual(mock_add.call_count, 3)
                self.assertEqual(mock_exec_command.call_count, 2)
                mock_exec_command.assert_has_calls(
                    self._EXPECTED_COMMAND_CALLS_SERVER_1
                )
