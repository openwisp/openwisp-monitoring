from unittest.mock import call, patch

from django.core import management
from django.core.exceptions import ValidationError
from django.test import TransactionTestCase
from swapper import load_model

from openwisp_controller.connection.settings import UPDATE_STRATEGIES
from openwisp_controller.connection.tests.utils import CreateConnectionsMixin, SshServer
from openwisp_monitoring.check.classes.iperf import get_iperf_schema
from openwisp_monitoring.check.classes.iperf import logger as iperf_logger

from ...device.tests import TestDeviceMonitoringMixin
from .. import settings
from ..classes import Iperf
from ..utils import run_iperf_checks_async
from .iperf_test_result import RESULT_FAIL, RESULT_TCP, RESULT_UDP

Chart = load_model('monitoring', 'Chart')
AlertSettings = load_model('monitoring', 'AlertSettings')
Metric = load_model('monitoring', 'Metric')
Check = load_model('check', 'Check')


class TestIperf(CreateConnectionsMixin, TestDeviceMonitoringMixin, TransactionTestCase):
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
            call(dc, 'iperf3 -c iperf.openwisptestserver.com -p 5201 -t 10 -J'),
            call(dc, 'iperf3 -c iperf.openwisptestserver.com -p 5201 -t 10 -u -J'),
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

    _IPERF = settings.CHECK_CLASSES[2][0]
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

    @patch.object(Iperf, '_exec_command')
    @patch.object(
        Iperf, '_get_iperf_servers', return_value=['iperf.openwisptestserver.com']
    )
    @patch.object(iperf_logger, 'warning')
    def test_iperf_check_no_params(
        self, mock_warn, mock_get_iperf_servers, mock_exec_command
    ):
        mock_exec_command.side_effect = [(RESULT_TCP, 0), (RESULT_UDP, 0)]

        # By default check params {}
        check, _ = self._create_iperf_test_env()
        result = check.perform_check(store=False)
        for key in self._RESULT_KEYS:
            self.assertIn(key, result)
        self.assertEqual(result['iperf_result'], 1)
        self.assertEqual(result['sent_bps_tcp'], 44.04)
        self.assertEqual(result['received_bytes_tcp'], 55.05)
        self.assertEqual(result['jitter'], 0.01)
        self.assertEqual(result['total_packets'], 40)
        self.assertEqual(mock_warn.call_count, 0)
        self.assertEqual(mock_exec_command.call_count, 2)
        mock_exec_command.assert_has_calls(self._EXPECTED_COMMAND_CALLS)
        mock_get_iperf_servers.assert_called_once_with(self.device.organization.id)

    @patch.object(Iperf, '_exec_command')
    @patch.object(
        Iperf, '_get_iperf_servers', return_value=['iperf.openwisptestserver.com']
    )
    @patch.object(iperf_logger, 'warning')
    def test_iperf_check_params(
        self, mock_warn, mock_get_iperf_servers, mock_exec_command
    ):
        mock_exec_command.side_effect = [(RESULT_TCP, 0), (RESULT_UDP, 0)]

        check, dc = self._create_iperf_test_env()
        test_params = {'port': 6201, 'time': 20}
        check.params = test_params
        check.save()
        self._EXPECTED_COMMAND_CALLS = [
            call(
                dc,
                f'iperf3 -c iperf.openwisptestserver.com -p {test_params["port"]} -t {test_params["time"]} -J',  # noqa
            ),
            call(
                dc,
                f'iperf3 -c iperf.openwisptestserver.com -p {test_params["port"]} -t {test_params["time"]} -u -J',  # noqa
            ),
        ]
        result = check.perform_check(store=False)
        for key in self._RESULT_KEYS:
            self.assertIn(key, result)
        self.assertEqual(result['iperf_result'], 1)
        self.assertEqual(result['sent_bps_tcp'], 44.04)
        self.assertEqual(result['received_bytes_tcp'], 55.05)
        self.assertEqual(result['jitter'], 0.01)
        self.assertEqual(result['total_packets'], 40)
        self.assertEqual(mock_warn.call_count, 0)
        self.assertEqual(mock_exec_command.call_count, 2)
        mock_exec_command.assert_has_calls(self._EXPECTED_COMMAND_CALLS)
        mock_get_iperf_servers.assert_called_once_with(self.device.organization.id)

    @patch.object(Iperf, '_exec_command')
    @patch.object(
        Iperf, '_get_iperf_servers', return_value=['iperf.openwisptestserver.com']
    )
    @patch.object(iperf_logger, 'warning')
    @patch.object(
        settings,
        'IPERF_CHECK_CONFIG',
        {
            'port': {'default': 9201},
            'time': {'default': 120},
        },
    )
    def test_iperf_check_config(
        self, mock_warn, mock_get_iperf_servers, mock_exec_command, *args
    ):
        mock_exec_command.side_effect = [(RESULT_TCP, 0), (RESULT_UDP, 0)]

        check, dc = self._create_iperf_test_env()
        self._EXPECTED_COMMAND_CALLS = [
            call(dc, 'iperf3 -c iperf.openwisptestserver.com -p 9201 -t 120 -J'),
            call(dc, 'iperf3 -c iperf.openwisptestserver.com -p 9201 -t 120 -u -J'),
        ]
        with patch.object(Iperf, 'schema', get_iperf_schema()):
            result = check.perform_check(store=False)
            for key in self._RESULT_KEYS:
                self.assertIn(key, result)
            self.assertEqual(result['iperf_result'], 1)
            self.assertEqual(result['sent_bps_tcp'], 44.04)
            self.assertEqual(result['received_bytes_tcp'], 55.05)
            self.assertEqual(result['jitter'], 0.01)
            self.assertEqual(result['total_packets'], 40)
            self.assertEqual(mock_warn.call_count, 0)
            self.assertEqual(mock_exec_command.call_count, 2)
            mock_exec_command.assert_has_calls(self._EXPECTED_COMMAND_CALLS)
            mock_get_iperf_servers.assert_called_once_with(self.device.organization.id)

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

        with self.subTest('Test device connection not working'):
            dc.is_working = False
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
        check, _ = self._create_iperf_test_env()
        invalid_params = [
            {'port': -1232},
            {'time': 0},
            {'port': 'invalid port'},
            {'time': 'invalid time'},
            {'port': '-12a'},
            {'time': '3test22'},
            {'port': 0},
            {'port': 797979},
            {'time': 36000},
            {'port': ''},
            {'time': ''},
        ]
        for invalid_params in invalid_params:
            check.params = invalid_params
            check.save()
            try:
                check.check_instance.validate()
            except ValidationError as e:
                self.assertIn('Invalid param', str(e))
            else:
                self.fail('ValidationError not raised')

    def test_iperf_check(self):
        check, _ = self._create_iperf_test_env()
        error = "ash: iperf3: not found"

        with self.subTest('Test iperf3 is not installed on the device'):
            with patch.object(
                Iperf, '_exec_command'
            ) as mock_exec_command, patch.object(
                Iperf,
                '_get_iperf_servers',
                return_value=['iperf.openwisptestserver.com'],
            ) as mock_get_iperf_servers:
                mock_exec_command.side_effect = [(error, 127)]
                with patch.object(iperf_logger, 'warning') as mock_warn:
                    check.perform_check(store=False)
                    mock_warn.assert_called_with(
                        f'Iperf3 is not installed on the "{self.device}", error - {error}'
                    )
                self.assertEqual(mock_warn.call_count, 1)
                self.assertEqual(mock_exec_command.call_count, 1)
                mock_get_iperf_servers.assert_called_once_with(
                    self.device.organization.id
                )

        with self.subTest('Test iperf check passes in both TCP & UDP'):
            with patch.object(
                Iperf, '_exec_command'
            ) as mock_exec_command, patch.object(
                Iperf,
                '_get_iperf_servers',
                return_value=['iperf.openwisptestserver.com'],
            ) as mock_get_iperf_servers, patch.object(
                iperf_logger, 'warning'
            ) as mock_warn:
                mock_exec_command.side_effect = [(RESULT_TCP, 0), (RESULT_UDP, 0)]
                self.assertEqual(Chart.objects.count(), 2)
                self.assertEqual(Metric.objects.count(), 2)
                result = check.perform_check(store=False)
                for key in self._RESULT_KEYS:
                    self.assertIn(key, result)

                self.assertEqual(result['iperf_result'], 1)
                self.assertEqual(result['sent_bps_tcp'], 44.04)
                self.assertEqual(result['received_bytes_tcp'], 55.05)
                self.assertEqual(result['retransmits'], 0)
                self.assertEqual(result['sent_bps_udp'], 1.05)
                self.assertEqual(result['sent_bytes_udp'], 1.31)
                self.assertEqual(result['jitter'], 0.01)
                self.assertEqual(result['total_packets'], 40)
                self.assertEqual(result['lost_packets'], 0)
                self.assertEqual(result['lost_percent'], 0.0)
                self.assertEqual(Chart.objects.count(), 10)
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
                mock_exec_command.assert_has_calls(self._EXPECTED_COMMAND_CALLS)
                mock_get_iperf_servers.assert_called_once_with(
                    self.device.organization.id
                )

        with self.subTest('Test iperf check fails in both TCP & UDP'):
            with patch.object(
                Iperf, '_exec_command'
            ) as mock_exec_command, patch.object(
                Iperf,
                '_get_iperf_servers',
                return_value=['iperf.openwisptestserver.com'],
            ) as mock_get_iperf_servers, patch.object(
                iperf_logger, 'warning'
            ) as mock_warn:
                mock_exec_command.side_effect = [(RESULT_FAIL, 1), (RESULT_FAIL, 1)]

                result = check.perform_check(store=False)
                for key in self._RESULT_KEYS:
                    self.assertIn(key, result)
                self.assertEqual(result['iperf_result'], 0)
                self.assertEqual(result['sent_bps_tcp'], 0.0)
                self.assertEqual(result['received_bps_tcp'], 0.0)
                self.assertEqual(result['jitter'], 0.0)
                self.assertEqual(result['total_packets'], 0)
                self.assertEqual(Chart.objects.count(), 10)
                self.assertEqual(Metric.objects.count(), 3)
                self.assertEqual(mock_exec_command.call_count, 2)
                mock_warn.assert_has_calls(self._EXPECTED_WARN_CALLS)
                mock_exec_command.assert_has_calls(self._EXPECTED_COMMAND_CALLS)
                mock_get_iperf_servers.assert_called_once_with(
                    self.device.organization.id
                )

        with self.subTest('Test iperf check TCP pass UDP fail'):
            with patch.object(
                Iperf, '_exec_command'
            ) as mock_exec_command, patch.object(
                Iperf,
                '_get_iperf_servers',
                return_value=['iperf.openwisptestserver.com'],
            ) as mock_get_iperf_servers, patch.object(
                iperf_logger, 'warning'
            ) as mock_warn:
                mock_exec_command.side_effect = [(RESULT_TCP, 0), (RESULT_FAIL, 1)]

                result = check.perform_check(store=False)
                for key in self._RESULT_KEYS:
                    self.assertIn(key, result)
                self.assertEqual(result['iperf_result'], 1)
                self.assertEqual(result['sent_bps_tcp'], 44.04)
                self.assertEqual(result['sent_bytes_tcp'], 55.05)
                self.assertEqual(result['jitter'], 0.0)
                self.assertEqual(result['total_packets'], 0)
                self.assertEqual(Chart.objects.count(), 10)
                self.assertEqual(Metric.objects.count(), 3)
                self.assertEqual(mock_exec_command.call_count, 2)
                mock_warn.assert_has_calls(self._EXPECTED_WARN_CALLS[1:])
                mock_exec_command.assert_has_calls(self._EXPECTED_COMMAND_CALLS)
                mock_get_iperf_servers.assert_called_once_with(
                    self.device.organization.id
                )

        with self.subTest('Test iperf check TCP fail UDP pass'):
            with patch.object(
                Iperf, '_exec_command'
            ) as mock_exec_command, patch.object(
                Iperf,
                '_get_iperf_servers',
                return_value=['iperf.openwisptestserver.com'],
            ) as mock_get_iperf_servers, patch.object(
                iperf_logger, 'warning'
            ) as mock_warn:
                mock_exec_command.side_effect = [(RESULT_FAIL, 1), (RESULT_UDP, 0)]

                result = check.perform_check(store=False)
                for key in self._RESULT_KEYS:
                    self.assertIn(key, result)
                self.assertEqual(result['iperf_result'], 1)
                self.assertEqual(result['sent_bps_tcp'], 0.0)
                self.assertEqual(result['received_bps_tcp'], 0.0)
                self.assertEqual(result['jitter'], 0.01)
                self.assertEqual(result['total_packets'], 40)
                self.assertEqual(Chart.objects.count(), 10)
                self.assertEqual(Metric.objects.count(), 3)
                self.assertEqual(mock_exec_command.call_count, 2)
                mock_warn.assert_has_calls(self._EXPECTED_WARN_CALLS[1:])
                mock_exec_command.assert_has_calls(self._EXPECTED_COMMAND_CALLS)
                mock_get_iperf_servers.assert_called_once_with(
                    self.device.organization.id
                )

    def test_iperf_check_utils(self):
        check, _ = self._create_iperf_test_env()

        with self.subTest('Test celery task run_iperf_checks'):
            with patch.object(
                Iperf, '_exec_command'
            ) as mock_exec_command, patch.object(
                Iperf,
                '_get_iperf_servers',
                return_value=['iperf.openwisptestserver.com'],
            ) as mock_get_iperf_servers, patch.object(
                iperf_logger, 'warning'
            ) as mock_warn:
                mock_exec_command.side_effect = [(RESULT_TCP, 0), (RESULT_UDP, 0)]

                run_iperf_checks_async()
                iperf_metric = Metric.objects.get(key='iperf')
                self.assertEqual(iperf_metric.content_object, self.device)
                points = iperf_metric.read(limit=None, extra_fields=self._RESULT_KEYS)
                for key in self._RESULT_KEYS:
                    self.assertIn(key, points[0])
                self.assertEqual(points[0]['iperf_result'], 1)
                self.assertEqual(mock_warn.call_count, 0)
                self.assertEqual(mock_exec_command.call_count, 2)
                mock_exec_command.assert_has_calls(self._EXPECTED_COMMAND_CALLS)
                mock_get_iperf_servers.assert_called_once_with(
                    self.device.organization.id
                )

        with self.subTest('Test management command run_iperf_checks'):
            with patch.object(
                Iperf, '_exec_command'
            ) as mock_exec_command, patch.object(
                Iperf,
                '_get_iperf_servers',
                return_value=['iperf.openwisptestserver.com'],
            ) as mock_get_iperf_servers, patch.object(
                iperf_logger, 'warning'
            ) as mock_warn:
                mock_exec_command.side_effect = [(RESULT_TCP, 0), (RESULT_UDP, 0)]

                management.call_command('run_iperf_checks')
                iperf_metric = Metric.objects.get(key='iperf')
                self.assertEqual(iperf_metric.content_object, self.device)
                points = iperf_metric.read(limit=None, extra_fields=self._RESULT_KEYS)
                self.assertEqual(len(points[0]), 14)
                self.assertEqual(points[0]['iperf_result'], 1)
                self.assertEqual(mock_warn.call_count, 0)
                self.assertEqual(mock_exec_command.call_count, 2)
                mock_exec_command.assert_has_calls(self._EXPECTED_COMMAND_CALLS)
                mock_get_iperf_servers.assert_called_once_with(
                    self.device.organization.id
                )
