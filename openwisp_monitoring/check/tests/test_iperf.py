from unittest import mock

from django.test import TransactionTestCase
from swapper import load_model

from openwisp_controller.connection.tests.utils import CreateConnectionsMixin, SshServer
from openwisp_monitoring.check.classes.iperf import logger as iperf_logger

from ...device.tests import TestDeviceMonitoringMixin
from .. import settings

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

    @mock.patch.object(iperf_logger, 'warning')
    def test_iperf_get_device_connection(self, mock_warn):
        ckey = self._create_credentials_with_key(port=self.ssh_server.port)
        dc = self._create_device_connection(credentials=ckey)
        device = dc.device
        check = Check.objects.get(check_type=self._IPERF)

        with self.subTest('Test device connection not working'):
            dc.is_working = False
            dc.save()
            check.perform_check(store=False)
            mock_warn.assert_called_with(
                f'Failed to get a working DeviceConnection for "{device}", iperf check skipped!'
            )

        # with self.subTest('Test active device connection when management tunnel down'):
        #     dc.is_working = True
        #     dc.save()
        #     auth_failed = AuthenticationException('Authentication failed.')
        #     with mock.patch(
        #         'openwisp_monitoring.check.classes.iperf.Iperf.connect',
        #         side_effect=auth_failed,
        #     ) as mocked_device_connection:
        #         check.perform_check(store=False)
