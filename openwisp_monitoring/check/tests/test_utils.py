import mock
from django.core import management

from ...device.tests import TestDeviceMonitoringMixin
from ..classes import Ping
from ..models import Check
from ..settings import CHECK_CLASSES
from ..utils import run_checks_async


class TestUtils(TestDeviceMonitoringMixin):
    _PING = CHECK_CLASSES[0][0]
    _FPING_OUTPUT = ('', bytes('10.40.0.1 : xmt/rcv/%loss = 5/5/0%, '
                               'min/avg/max = 0.04/0.08/0.15', 'utf8'))

    def _create_check(self):
        config = self._create_config(organization=self._create_org())
        config.last_ip = '10.40.0.1'
        config.save()
        check = Check(name='Ping check',
                      check=self._PING,
                      content_object=config.device,
                      params={})
        check.full_clean()
        check.save()
        return check

    @mock.patch.object(Ping, '_command', return_value=_FPING_OUTPUT)
    def test_run_checks_async_success(self, mocked_method):
        self._create_check()
        run_checks_async()

    @mock.patch.object(Ping, '_command', return_value=_FPING_OUTPUT)
    def test_management_command(self, mocked_method):
        self._create_check()
        management.call_command('run_checks')
