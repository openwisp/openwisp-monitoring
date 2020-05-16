import os
from unittest import skipUnless

from django.test import TransactionTestCase
from openwisp_monitoring.check.base.tests.test_models import BaseTestModels
from openwisp_monitoring.check.base.tests.test_ping import BaseTestPing
from openwisp_monitoring.check.base.tests.test_utils import BaseTestUtils
from openwisp_monitoring.check.models import Check
from openwisp_monitoring.device.tests import TestDeviceMonitoringMixin


@skipUnless(
    os.environ.get('SAMPLE_APP', False), 'Running tests on standard openwisp_monitoring'
)
class TestUtils(BaseTestUtils, TestDeviceMonitoringMixin, TransactionTestCase):
    app_label = 'check'
    check_model = Check


@skipUnless(
    os.environ.get('SAMPLE_APP', False), 'Running tests on standard openwisp_monitoring'
)
class TestPing(BaseTestPing, TestDeviceMonitoringMixin, TransactionTestCase):
    app_label = 'check'
    check_model = Check


@skipUnless(
    os.environ.get('SAMPLE_APP', False), 'Running tests on standard openwisp_monitoring'
)
class TestModels(BaseTestModels, TestDeviceMonitoringMixin, TransactionTestCase):
    app_label = 'check'
    check_model = Check
