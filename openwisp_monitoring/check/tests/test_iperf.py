from unittest import mock

from django.test import TransactionTestCase
from swapper import load_model

from openwisp_controller.connection.tests.utils import CreateConnectionsMixin, SshServer
from openwisp_monitoring.check.classes.iperf import logger as iperf_logger

from ...device.tests import TestDeviceMonitoringMixin
from .. import settings
from ..classes import Iperf

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
        'sent_bps',
        'received_bps',
        'sent_bytes',
        'received_bytes',
        'retransmits',
        'jitter',
        'packets',
        'lost_packets',
        'lost_percent',
    ]

    @mock.patch.object(iperf_logger, 'warning')
    def test_iperf_get_device_connection(self, mock_warn):
        ckey = self._create_credentials_with_key(port=self.ssh_server.port)
        device = self._create_device()
        self._create_config(device=device)
        dc = self._create_device_connection(device=device, credentials=ckey)
        check = Check(
            name='Iperf check',
            check_type=self._IPERF,
            content_object=device,
        )
        with self.subTest('Test inactive or invalid device connection'):
            check.perform_check(store=False)
            mock_warn.assert_called_with(
                f'DeviceConnection is not properly set for "{device}", iperf check skipped!'
            )
        with self.subTest('Test active device connection when management tunnel down'):
            dc.is_working = True
            dc.save()
            # Todo : Need to change this mock
            with mock.patch.object(
                Iperf, '_connect', return_value=False
            ) as mocked_connect:
                check.perform_check(store=False)
                mock_warn.assert_called_with(
                    f'Failed to get a working DeviceConnection for "{device}", iperf check skipped!'
                )
            self.assertEqual(mocked_connect.call_count, 1)
