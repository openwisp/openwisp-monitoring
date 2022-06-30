from unittest.mock import call, patch

from django.test import TransactionTestCase
from swapper import load_model

from openwisp_controller.connection.tests.utils import CreateConnectionsMixin, SshServer
from openwisp_monitoring.check.classes.iperf import logger as iperf_logger

from ...device.tests import TestDeviceMonitoringMixin
from .. import settings
from ..classes import Iperf
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

    @patch.object(iperf_logger, 'warning')
    def test_iperf_get_device_connection(self, mock_warn):
        ckey = self._create_credentials_with_key(port=self.ssh_server.port)
        dc = self._create_device_connection(credentials=ckey)
        device = dc.device
        check = Check.objects.get(check_type=self._IPERF)

        with self.subTest('Test active device connection when management tunnel down'):
            dc.is_working = True
            dc.save()
            with patch.object(Iperf, '_connect', return_value=False) as mocked_connect:
                check.perform_check(store=False)
                mock_warn.assert_called_with(
                    f'DeviceConnection for "{device}" is not working, iperf check skipped!'
                )
            mocked_connect.assert_called_once_with(dc)
            self.assertEqual(mocked_connect.call_count, 1)

        with self.subTest('Test device connection not working'):
            dc.is_working = False
            dc.save()
            check.perform_check(store=False)
            mock_warn.assert_called_with(
                f'Failed to get a working DeviceConnection for "{device}", iperf check skipped!'
            )

    @patch.object(
        Iperf, '_exec_command', side_effect=[(RESULT_TCP, 0), (RESULT_UDP, 0)]
    )
    @patch.object(
        Iperf, '_get_iperf_servers', return_value=['iperf.openwisptestserver.com']
    )
    def test_iperf_check(self, mock_get_iperf_servers, mock_exec_command):

        ckey = self._create_credentials_with_key(port=self.ssh_server.port)
        dc = self._create_device_connection(credentials=ckey)
        dc.connect()
        device = dc.device
        check = Check.objects.get(check_type=self._IPERF)
        expected_exec_command_calls = [
            call(dc, 'iperf3 -c iperf.openwisptestserver.com -J'),
            call(dc, 'iperf3 -c iperf.openwisptestserver.com -u -J'),
        ]
        self.assertEqual(Chart.objects.count(), 2)
        self.assertEqual(Metric.objects.count(), 2)
        check.perform_check(store=False)
        iperf_metric = Metric.objects.get(key='iperf').read()[0]
        self.assertEqual(iperf_metric['iperf_result'], 1)
        self.assertEqual(Chart.objects.count(), 10)
        self.assertEqual(Metric.objects.count(), 3)
        mock_get_iperf_servers.assert_called_once_with(device.organization.id)
        self.assertEqual(mock_exec_command.call_count, 2)
        mock_exec_command.assert_has_calls(expected_exec_command_calls)

    @patch.object(Iperf, '_exec_command')
    @patch.object(
        Iperf, '_get_iperf_servers', return_value=['iperf.openwisptestserver.com']
    )
    @patch.object(iperf_logger, 'warning')
    def test_iperf_check_fail(
        self, mock_warn, mock_get_iperf_servers, mock_exec_command
    ):
        mock_exec_command.side_effect = [(RESULT_FAIL, 1), (RESULT_FAIL, 1)]
        ckey = self._create_credentials_with_key(port=self.ssh_server.port)
        dc = self._create_device_connection(credentials=ckey)
        dc.connect()
        device = dc.device
        check = Check.objects.get(check_type=self._IPERF)
        expected_exec_command_calls = [
            call(dc, 'iperf3 -c iperf.openwisptestserver.com -J'),
            call(dc, 'iperf3 -c iperf.openwisptestserver.com -u -J'),
        ]
        expected_mock_warns = [
            call(
                f'Iperf check failed for "{device}", error - unable to connect to server: Connection refused'
            ),
            call(
                f'Iperf check failed for "{device}", error - unable to connect to server: Connection refused'
            ),
        ]
        self.assertEqual(Chart.objects.count(), 0)
        self.assertEqual(Metric.objects.count(), 0)
        check.perform_check(store=False)
        self.assertEqual(mock_warn.call_count, 2)
        mock_warn.assert_has_calls(expected_mock_warns)
        iperf_metric = Metric.objects.get(key='iperf').read()[0]
        self.assertEqual(iperf_metric['iperf_result'], 0)
        self.assertEqual(Chart.objects.count(), 8)
        self.assertEqual(Metric.objects.count(), 1)
        mock_get_iperf_servers.assert_called_once_with(device.organization.id)
        self.assertEqual(mock_exec_command.call_count, 2)
        mock_exec_command.assert_has_calls(expected_exec_command_calls)
