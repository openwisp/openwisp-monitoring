from unittest.mock import patch

from django.test import TransactionTestCase
from django.utils.timezone import now
from swapper import load_model

from openwisp_monitoring.check.classes import Ping
from openwisp_monitoring.check.tests import _FPING_REACHABLE
from openwisp_monitoring.check.tests.test_models import TestModels as BaseTestModels
from openwisp_monitoring.check.tests.test_ping import TestPing as BaseTestPing
from openwisp_monitoring.check.tests.test_utils import TestUtils as BaseTestUtils
from openwisp_monitoring.device.tests import TestDeviceMonitoringMixin

Check = load_model('check', 'Check')


class TestUtils(BaseTestUtils, TestDeviceMonitoringMixin, TransactionTestCase):
    pass


class TestPing(BaseTestPing, TestDeviceMonitoringMixin, TransactionTestCase):
    pass


class TestModels(BaseTestModels, TestDeviceMonitoringMixin, TransactionTestCase):
    @patch.object(Ping, '_command', return_value=_FPING_REACHABLE)
    def test_last_called(self, mocked_method):
        device = self._create_device(organization=self._create_org())
        # will ping localhost
        device.management_ip = '127.0.0.1'
        check = Check(
            name='Ping check',
            check_type=self._PING,
            content_object=device,
            params={'count': 2, 'interval': 10, 'bytes': 12, 'timeout': 50},
        )
        check.perform_check(store=False)
        # Avoid any failures due to minor lag
        lag = int(now().strftime('%s')) - int(check.last_called.strftime('%s'))
        self.assertLessEqual(lag, 4)


# this is necessary to avoid excuting the base test suites
del BaseTestModels
del BaseTestPing
del BaseTestUtils
