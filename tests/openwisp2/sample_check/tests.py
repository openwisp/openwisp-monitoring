from django.test import TransactionTestCase
from openwisp_monitoring.check.tests.test_models import TestModels as BaseTestModels
from openwisp_monitoring.check.tests.test_ping import TestPing as BaseTestPing
from openwisp_monitoring.check.tests.test_utils import TestUtils as BaseTestUtils
from openwisp_monitoring.device.tests import TestDeviceMonitoringMixin
from swapper import load_model

Check = load_model('check', 'Check')


class TestUtils(BaseTestUtils, TestDeviceMonitoringMixin, TransactionTestCase):
    pass


class TestPing(BaseTestPing, TestDeviceMonitoringMixin, TransactionTestCase):
    pass


class TestModels(BaseTestModels, TestDeviceMonitoringMixin, TransactionTestCase):
    pass


del BaseTestModels
del BaseTestPing
del BaseTestUtils
