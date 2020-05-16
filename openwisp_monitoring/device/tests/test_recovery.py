import os
from unittest import skipIf

from ..base.tests.test_recovery import BaseTestRecovery
from . import DeviceMonitoringTestCase


@skipIf(os.environ.get('SAMPLE_APP', False), 'Running tests on SAMPLE_APP')
class TestRecovery(BaseTestRecovery, DeviceMonitoringTestCase):
    app_name = 'device_monitoring'
