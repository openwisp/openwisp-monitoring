from json import loads
from unittest.mock import call, patch

from django.core.exceptions import ValidationError
from django.test import TransactionTestCase
from swapper import load_model

from openwisp_controller.connection.settings import UPDATE_STRATEGIES
from openwisp_controller.connection.tests.utils import CreateConnectionsMixin, SshServer
from openwisp_monitoring.check.classes.iperf import get_iperf_schema
from openwisp_monitoring.check.classes.iperf import logger as iperf_logger

from ...device.tests import TestDeviceMonitoringMixin
from .. import settings as app_settings
from ..classes import Iperf
from .iperf_test_utils import (
    INVALID_PARAMS,
    PARAM_ERROR,
    RESULT_AUTH_FAIL,
    RESULT_FAIL,
    RESULT_TCP,
    RESULT_UDP,
    TEST_RSA_KEY,
)

Chart = load_model('monitoring', 'Chart')
AlertSettings = load_model('monitoring', 'AlertSettings')
Metric = load_model('monitoring', 'Metric')
Check = load_model('check', 'Check')
Notification = load_model('openwisp_notifications', 'Notification')


class TestIperf(CreateConnectionsMixin, TestDeviceMonitoringMixin, TransactionTestCase):

    _IPERF = app_settings.CHECK_CLASSES[2][0]
    _RESULT_KEYS = [
        'iperf_result',
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

    def _create_iperf_test_env(self):
        ckey = self._create_credentials_with_key(port=self.ssh_server.port)
        dc = self._create_device_connection(credentials=ckey)
        dc.connect()
        self.device = dc.device
        self._EXPECTED_COMMAND_CALLS = [
            call(dc, 'iperf3 -c iperf.openwisptestserver.com -p 5201 -t 10 -b 0 -J'),
            call(
                dc, 'iperf3 -c iperf.openwisptestserver.com -p 5201 -t 10 -b 30M -u -J'
            ),
        ]
        self._EXPECTED_WARN_CALLS = [
            call(
                f'Iperf check failed for "{self.device}", error - unable to connect to server: Connection refused'  # noqa
            ),
            call(
                f'Iperf check failed for "{self.device}", error - unable to connect to server: Connection refused'  # noqa
            ),
        ]
        check = Check.objects.get(check_type=self._IPERF)
        return check, dc

    def _set_auth_expected_calls(self, dc, org_id, config):
        password = config[org_id]['password']
        username = config[org_id]['username']
        server = 'iperf.openwisptestserver.com'
        test_prefix = '-----BEGIN PUBLIC KEY-----\n'
        test_suffix = '\n-----END PUBLIC KEY-----'
        key = config[org_id]['rsa_public_key']
        rsa_key_path = '/tmp/iperf-public-key.pem'

        self._EXPECTED_COMMAND_CALLS = [
            call(
                dc,
                f'echo "{test_prefix}{key}{test_suffix}" > {rsa_key_path} && \
            IPERF3_PASSWORD="{password}" iperf3 -c {server} -p 5201 -t 10 \
            --username "{username}" --rsa-public-key-path {rsa_key_path} -b 0 -J',
            ),
            call(
                dc,
                f'IPERF3_PASSWORD="{password}" iperf3 -c {server} -p 5201 -t 10 \
            --username "{username}" --rsa-public-key-path {rsa_key_path} -b 30M -u -J && rm {rsa_key_path}',
            ),
        ]

    def _assert_iperf_fail_result(self, result):
        for key in self._RESULT_KEYS:
            self.assertIn(key, result)
        self.assertEqual(result['iperf_result'], 0)
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

    @patch.object(Iperf, '_exec_command')
    @patch.object(
        Iperf, '_get_iperf_servers', return_value='iperf.openwisptestserver.com'
    )
    @patch.object(iperf_logger, 'warning')
    def test_iperf_check_no_params(
        self, mock_warn, mock_get_iperf_servers, mock_exec_command
    ):
        mock_exec_command.side_effect = [(RESULT_TCP, 0), (RESULT_UDP, 0)]

        # By default check params {}
        check, _ = self._create_iperf_test_env()
        tcp_result = loads(RESULT_TCP)['end']
        udp_result = loads(RESULT_UDP)['end']['sum']
        result = check.perform_check(store=False)
        for key in self._RESULT_KEYS:
            self.assertIn(key, result)
        self.assertEqual(result['iperf_result'], 1)
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
        self.assertEqual(mock_get_iperf_servers.call_count, 1)
        mock_exec_command.assert_has_calls(self._EXPECTED_COMMAND_CALLS)

    @patch.object(Iperf, '_exec_command')
    @patch.object(
        Iperf, '_get_iperf_servers', return_value='iperf.openwisptestserver.com'
    )
    @patch.object(iperf_logger, 'warning')
    def test_iperf_check_params(
        self, mock_warn, mock_get_iperf_servers, mock_exec_command
    ):
        mock_exec_command.side_effect = [(RESULT_TCP, 0), (RESULT_UDP, 0)]
        tcp_result = loads(RESULT_TCP)['end']
        udp_result = loads(RESULT_UDP)['end']['sum']
        check, dc = self._create_iperf_test_env()
        server = 'iperf.openwisptestserver.com'
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
                'tcp': {'bitrate': '10M'},
                'udp': {'bitrate': '30M'},
            },
        }
        time = test_params['client_options']['time']
        port = test_params['client_options']['port']
        tcp_bitrate = test_params['client_options']['tcp']['bitrate']
        udp_bitrate = test_params['client_options']['udp']['bitrate']
        username = test_params['username']
        password = test_params['password']
        key = test_params['rsa_public_key']
        rsa_key_path = '/tmp/iperf-public-key.pem'
        check.params = test_params
        check.save()
        self._EXPECTED_COMMAND_CALLS = [
            call(
                dc,
                f'echo "{test_prefix}{key}{test_suffix}" > {rsa_key_path} && \
            IPERF3_PASSWORD="{password}" iperf3 -c {server} -p {port} -t {time} \
            --username "{username}" --rsa-public-key-path {rsa_key_path} -b {tcp_bitrate} -J',
            ),
            call(
                dc,
                f'IPERF3_PASSWORD="{password}" iperf3 -c {server} -p {port} -t {time} \
            --username "{username}" --rsa-public-key-path {rsa_key_path} -b {udp_bitrate} -u -J && rm {rsa_key_path}',  # noqa
            ),
        ]
        result = check.perform_check(store=False)
        for key in self._RESULT_KEYS:
            self.assertIn(key, result)
        self.assertEqual(result['iperf_result'], 1)
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
        self.assertEqual(mock_get_iperf_servers.call_count, 1)
        mock_exec_command.assert_has_calls(self._EXPECTED_COMMAND_CALLS)

    @patch.object(Iperf, '_exec_command')
    @patch.object(
        Iperf, '_get_iperf_servers', return_value='iperf.openwisptestserver.com'
    )
    @patch.object(iperf_logger, 'warning')
    def test_iperf_check_config(
        self, mock_warn, mock_get_iperf_servers, mock_exec_command
    ):
        mock_exec_command.side_effect = [(RESULT_TCP, 0), (RESULT_UDP, 0)]
        tcp_result = loads(RESULT_TCP)['end']
        udp_result = loads(RESULT_UDP)['end']['sum']
        check, dc = self._create_iperf_test_env()
        self._EXPECTED_COMMAND_CALLS = [
            call(dc, 'iperf3 -c iperf.openwisptestserver.com -p 9201 -t 120 -b 10M -J'),
            call(
                dc, 'iperf3 -c iperf.openwisptestserver.com -p 9201 -t 120 -b 50M -u -J'
            ),
        ]
        org_id = str(self.device.organization.id)
        iperf_config = {
            org_id: {
                'client_options': {
                    'port': 9201,
                    'time': 120,
                    'tcp': {'bitrate': '10M'},
                    'udp': {'bitrate': '50M'},
                }
            }
        }
        with patch.object(app_settings, 'IPERF_CHECK_CONFIG', iperf_config):
            with patch.object(Iperf, 'schema', get_iperf_schema()):
                result = check.perform_check(store=False)
                for key in self._RESULT_KEYS:
                    self.assertIn(key, result)
                self.assertEqual(result['iperf_result'], 1)
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
                self.assertEqual(mock_get_iperf_servers.call_count, 1)
                mock_exec_command.assert_has_calls(self._EXPECTED_COMMAND_CALLS)

    @patch.object(iperf_logger, 'warning')
    def test_iperf_device_connection(self, mock_warn):
        check, dc = self._create_iperf_test_env()

        with self.subTest('Test active device connection when management tunnel down'):
            with patch.object(Iperf, '_connect', return_value=False) as mocked_connect:
                check.perform_check(store=False)
                mock_warn.assert_called_with(
                    f'DeviceConnection for "{self.device}" is not working, iperf check skipped!'
                )
            mocked_connect.assert_called_once_with(dc)
            self.assertEqual(mocked_connect.call_count, 1)

        with self.subTest('Test device connection is not enabled'):
            dc.enabled = False
            dc.save()
            check.perform_check(store=False)
            mock_warn.assert_called_with(
                f'Failed to get a working DeviceConnection for "{self.device}", iperf check skipped!'
            )

        with self.subTest('Test device connection is not with right update strategy'):
            dc.update_strategy = UPDATE_STRATEGIES[1][0]
            dc.is_working = True
            dc.enabled = True
            dc.save()
            check.perform_check(store=False)
            mock_warn.assert_called_with(
                f'Failed to get a working DeviceConnection for "{self.device}", iperf check skipped!'
            )

    def test_iperf_check_content_object_none(self):
        check = Check(name='Iperf check', check_type=self._IPERF, params={})
        try:
            check.check_instance.validate()
        except ValidationError as e:
            self.assertIn('device', str(e))
        else:
            self.fail('ValidationError not raised')

    def test_iperf_check_content_object_not_device(self):
        check = Check(
            name='Iperf check',
            check_type=self._IPERF,
            content_object=self._create_user(),
            params={},
        )
        try:
            check.check_instance.validate()
        except ValidationError as e:
            self.assertIn('device', str(e))
        else:
            self.fail('ValidationError not raised')

    def test_iperf_check_schema_violation(self):
        device = self._create_device(organization=self._create_org())
        for invalid_param in INVALID_PARAMS:
            check = Check(
                name='Iperf check',
                check_type=self._IPERF,
                content_object=device,
                params=invalid_param,
            )
            try:
                check.check_instance.validate()
            except ValidationError as e:
                self.assertIn('Invalid param', str(e))
            else:
                self.fail('ValidationError not raised')

    @patch.object(Iperf, '_exec_command')
    @patch.object(
        Iperf, '_get_iperf_servers', return_value='iperf.openwisptestserver.com'
    )
    @patch.object(iperf_logger, 'warning')
    def test_iperf_check(self, mock_warn, mock_get_iperf_servers, mock_exec_command):
        check, _ = self._create_iperf_test_env()
        error = "ash: iperf3: not found"
        tcp_result = loads(RESULT_TCP)['end']
        udp_result = loads(RESULT_UDP)['end']['sum']

        with self.subTest('Test iperf3 is not installed on the device'):
            mock_exec_command.side_effect = [(error, 127)]
            check.perform_check(store=False)
            mock_warn.assert_called_with(
                f'Iperf3 is not installed on the "{self.device}", error - {error}'
            )
            self.assertEqual(mock_warn.call_count, 1)
            self.assertEqual(mock_exec_command.call_count, 1)
            self.assertEqual(mock_get_iperf_servers.call_count, 1)
            mock_exec_command.reset_mock()
            mock_get_iperf_servers.reset_mock()
            mock_warn.reset_mock()

        with self.subTest('Test iperf3 errors not in json format'):
            org_id = str(self.device.organization.id)
            iperf_config = {
                org_id: {
                    'username': 'test',
                    'password': 'testpass',
                    'rsa_public_key': 'INVALID_RSA_KEY',
                }
            }
            with patch.object(app_settings, 'IPERF_CHECK_CONFIG', iperf_config):
                mock_exec_command.side_effect = [(PARAM_ERROR, 1), (PARAM_ERROR, 1)]
                EXPECTED_WARN_CALLS = [
                    call(
                        f'Iperf check failed for "{self.device}", error - {PARAM_ERROR}'
                    ),
                    call(
                        f'Iperf check failed for "{self.device}", error - {PARAM_ERROR}'
                    ),
                ]
                check.perform_check(store=False)
                self.assertEqual(mock_warn.call_count, 2)
                self.assertEqual(mock_exec_command.call_count, 2)
                self.assertEqual(mock_get_iperf_servers.call_count, 1)
                mock_warn.assert_has_calls(EXPECTED_WARN_CALLS)
                mock_exec_command.reset_mock()
                mock_get_iperf_servers.reset_mock()
                mock_warn.reset_mock()

        with self.subTest('Test iperf check passes in both TCP & UDP'):
            mock_exec_command.side_effect = [(RESULT_TCP, 0), (RESULT_UDP, 0)]
            self.assertEqual(Chart.objects.count(), 2)
            self.assertEqual(Metric.objects.count(), 2)
            result = check.perform_check(store=False)
            for key in self._RESULT_KEYS:
                self.assertIn(key, result)
            self.assertEqual(result['iperf_result'], 1)
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

            iperf_metric = Metric.objects.get(key='iperf')
            self.assertEqual(Metric.objects.count(), 3)
            self.assertEqual(iperf_metric.content_object, self.device)
            points = iperf_metric.read(limit=None, extra_fields=list(result.keys()))
            self.assertEqual(len(points), 1)
            self.assertEqual(points[0]['iperf_result'], result['iperf_result'])
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
            self.assertEqual(mock_get_iperf_servers.call_count, 1)
            mock_exec_command.assert_has_calls(self._EXPECTED_COMMAND_CALLS)
            mock_exec_command.reset_mock()
            mock_get_iperf_servers.reset_mock()
            mock_warn.reset_mock()

        with self.subTest('Test iperf check fails in both TCP & UDP'):
            mock_exec_command.side_effect = [(RESULT_FAIL, 1), (RESULT_FAIL, 1)]

            result = check.perform_check(store=False)
            self._assert_iperf_fail_result(result)
            self.assertEqual(Chart.objects.count(), 8)
            self.assertEqual(Metric.objects.count(), 3)
            self.assertEqual(mock_exec_command.call_count, 2)
            self.assertEqual(mock_get_iperf_servers.call_count, 1)
            mock_warn.assert_has_calls(self._EXPECTED_WARN_CALLS)
            mock_exec_command.assert_has_calls(self._EXPECTED_COMMAND_CALLS)
            mock_exec_command.reset_mock()
            mock_get_iperf_servers.reset_mock()
            mock_warn.reset_mock()

        with self.subTest('Test iperf check TCP pass UDP fail'):
            mock_exec_command.side_effect = [(RESULT_TCP, 0), (RESULT_FAIL, 1)]

            result = check.perform_check(store=False)
            for key in self._RESULT_KEYS:
                self.assertIn(key, result)
            self.assertEqual(result['iperf_result'], 1)
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
            self.assertEqual(mock_exec_command.call_count, 2)
            self.assertEqual(mock_get_iperf_servers.call_count, 1)
            mock_warn.assert_has_calls(self._EXPECTED_WARN_CALLS[1:])
            mock_exec_command.assert_has_calls(self._EXPECTED_COMMAND_CALLS)
            mock_exec_command.reset_mock()
            mock_get_iperf_servers.reset_mock()
            mock_warn.reset_mock()

        with self.subTest('Test iperf check TCP fail UDP pass'):
            mock_exec_command.side_effect = [(RESULT_FAIL, 1), (RESULT_UDP, 0)]

            result = check.perform_check(store=False)
            for key in self._RESULT_KEYS:
                self.assertIn(key, result)
            self.assertEqual(result['iperf_result'], 1)
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
            self.assertEqual(mock_exec_command.call_count, 2)
            self.assertEqual(mock_get_iperf_servers.call_count, 1)
            mock_warn.assert_has_calls(self._EXPECTED_WARN_CALLS[1:])
            mock_exec_command.assert_has_calls(self._EXPECTED_COMMAND_CALLS)

    @patch.object(Iperf, '_exec_command')
    @patch.object(
        Iperf, '_get_iperf_servers', return_value='iperf.openwisptestserver.com'
    )
    @patch.object(iperf_logger, 'warning')
    def test_iperf_check_auth_config(
        self, mock_warn, mock_get_iperf_servers, mock_exec_command
    ):

        check, dc = self._create_iperf_test_env()
        org_id = str(self.device.organization.id)
        iperf_config = {
            org_id: {
                'username': 'test',
                'password': 'testpass',
                'rsa_public_key': TEST_RSA_KEY,
            }
        }
        iperf_conf_wrong_pass = {
            org_id: {
                'username': 'test',
                'password': 'wrongpass',
                'rsa_public_key': TEST_RSA_KEY,
            }
        }
        iperf_conf_wrong_user = {
            org_id: {
                'username': 'wronguser',
                'password': 'testpass',
                'rsa_public_key': TEST_RSA_KEY,
            }
        }
        auth_error = "test authorization failed"
        tcp_result = loads(RESULT_TCP)['end']
        udp_result = loads(RESULT_UDP)['end']['sum']

        self._EXPECTED_WARN_CALLS = [
            call(f'Iperf check failed for "{self.device}", error - {auth_error}'),
            call(f'Iperf check failed for "{self.device}", error - {auth_error}'),
        ]
        with self.subTest('Test iperf check with right config'):
            with patch.object(
                app_settings,
                'IPERF_CHECK_CONFIG',
                iperf_config
                # It is required to mock "Iperf.schema" here so that it
                # uses the updated configuration from "IPERF_CHECK_CONFIG" setting.
            ), patch.object(Iperf, 'schema', get_iperf_schema()):
                self._set_auth_expected_calls(dc, org_id, iperf_config)
                mock_exec_command.side_effect = [(RESULT_TCP, 0), (RESULT_UDP, 0)]

                result = check.perform_check(store=False)
                for key in self._RESULT_KEYS:
                    self.assertIn(key, result)
                self.assertEqual(result['iperf_result'], 1)
                self.assertEqual(
                    result['sent_bps_tcp'], tcp_result['sum_sent']['bits_per_second']
                )
                self.assertEqual(
                    result['received_bytes_tcp'], tcp_result['sum_received']['bytes']
                )
                self.assertEqual(result['jitter'], udp_result['jitter_ms'])
                self.assertEqual(result['total_packets'], udp_result['packets'])
                self.assertEqual(mock_exec_command.call_count, 2)
                self.assertEqual(mock_get_iperf_servers.call_count, 1)
                mock_exec_command.assert_has_calls(self._EXPECTED_COMMAND_CALLS)
            mock_exec_command.reset_mock()
            mock_get_iperf_servers.reset_mock()
            mock_warn.reset_mock()

        with self.subTest('Test iperf check with wrong password'):
            with patch.object(
                app_settings, 'IPERF_CHECK_CONFIG', iperf_conf_wrong_pass
            ), patch.object(Iperf, 'schema', get_iperf_schema()):
                self._set_auth_expected_calls(dc, org_id, iperf_conf_wrong_pass)
                mock_exec_command.side_effect = [
                    (RESULT_AUTH_FAIL, 1),
                    (RESULT_AUTH_FAIL, 1),
                ]

                result = check.perform_check(store=False)
                self._assert_iperf_fail_result(result)
                self.assertEqual(mock_exec_command.call_count, 2)
                mock_warn.assert_has_calls(self._EXPECTED_WARN_CALLS)
                mock_exec_command.assert_has_calls(self._EXPECTED_COMMAND_CALLS)
                self.assertEqual(mock_get_iperf_servers.call_count, 1)
            mock_exec_command.reset_mock()
            mock_get_iperf_servers.reset_mock()
            mock_warn.reset_mock()

        with self.subTest('Test iperf check with wrong username'):
            with patch.object(
                app_settings, 'IPERF_CHECK_CONFIG', iperf_conf_wrong_user
            ), patch.object(Iperf, 'schema', get_iperf_schema()):
                self._set_auth_expected_calls(dc, org_id, iperf_conf_wrong_user)
                mock_exec_command.side_effect = [
                    (RESULT_AUTH_FAIL, 1),
                    (RESULT_AUTH_FAIL, 1),
                ]

                result = check.perform_check(store=False)
                self._assert_iperf_fail_result(result)
                self.assertEqual(mock_exec_command.call_count, 2)
                mock_warn.assert_has_calls(self._EXPECTED_WARN_CALLS)
                mock_exec_command.assert_has_calls(self._EXPECTED_COMMAND_CALLS)
                self.assertEqual(mock_get_iperf_servers.call_count, 1)
