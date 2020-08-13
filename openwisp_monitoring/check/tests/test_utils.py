from unittest.mock import patch

from django.core import management
from django.test import TransactionTestCase
from swapper import load_model

from ...device.tests import TestDeviceMonitoringMixin
from ..classes import Ping
from ..settings import CHECK_CLASSES
from ..tasks import perform_check
from ..utils import run_checks_async
from . import _FPING_REACHABLE

Check = load_model('check', 'Check')


class TestUtils(TestDeviceMonitoringMixin, TransactionTestCase):
    _PING = CHECK_CLASSES[0][0]

    def _create_check(self):
        device = self._create_device(organization=self._create_org())
        device.last_ip = '10.40.0.1'
        device.save()
        # check is automatically created via django signal

    @patch.object(Ping, '_command', return_value=_FPING_REACHABLE)
    def test_run_checks_async_success(self, mocked_method):
        self._create_check()
        run_checks_async()

    @patch.object(Ping, '_command', return_value=_FPING_REACHABLE)
    def test_management_command(self, mocked_method):
        self._create_check()
        management.call_command('run_checks')

    @patch('logging.Logger.warning')
    def test_perform_check_task_resiliency(self, mock):
        check = Check(name='Test check')
        perform_check.delay(check.pk)
        mock.assert_called_with(f'The check with uuid {check.pk} has been deleted')
