from unittest.mock import patch

from django.core import management
from django.test import TransactionTestCase

from ...device.tests import TestDeviceMonitoringMixin
from ..classes import Ping
from ..settings import CHECK_CLASSES
from ..utils import run_checks_async


class TestUtils(TestDeviceMonitoringMixin, TransactionTestCase):
    _PING = CHECK_CLASSES[0][0]
    _FPING_OUTPUT = ('', bytes('10.40.0.1 : xmt/rcv/%loss = 5/5/0%, '
                               'min/avg/max = 0.04/0.08/0.15', 'utf8'))

    def _create_check(self):
        device = self._create_device(organization=self._create_org())
        device.last_ip = '10.40.0.1'
        device.save()
        # check is automatically created via django signal

    @patch.object(Ping, '_command', return_value=_FPING_OUTPUT)
    def test_run_checks_async_success(self, mocked_method):
        self._create_check()
        run_checks_async()

    @patch.object(Ping, '_command', return_value=_FPING_OUTPUT)
    def test_management_command(self, mocked_method):
        self._create_check()
        management.call_command('run_checks')
