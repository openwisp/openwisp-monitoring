import os
from unittest import skipIf

from ..base.tests.test_settings import BaseTestSettings
from . import DeviceMonitoringTestCase


@skipIf(os.environ.get('SAMPLE_APP', False), 'Running tests on SAMPLE_APP')
class TestSettings(BaseTestSettings, DeviceMonitoringTestCase):
    app_name = 'device_monitoring'
