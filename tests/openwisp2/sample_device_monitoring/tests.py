import os
from unittest import skipUnless

from openwisp_monitoring.device.base.tests.test_models import (
    BaseTestCase,
    BaseTestDeviceData,
    BaseTestDeviceMonitoring,
)
from openwisp_monitoring.device.base.tests.test_recovery import BaseTestRecovery
from openwisp_monitoring.device.base.tests.test_settings import BaseTestSettings
from openwisp_monitoring.device.models import DeviceData
from openwisp_monitoring.device.tests import DeviceMonitoringTestCase


@skipUnless(
    os.environ.get('SAMPLE_APP', False), 'Running tests on standard openwisp_monitoring'
)
class TestRecovery(BaseTestRecovery, DeviceMonitoringTestCase):
    app_name = 'device_monitoring'


@skipUnless(
    os.environ.get('SAMPLE_APP', False), 'Running tests on standard openwisp_monitoring'
)
class TestDeviceData(BaseTestDeviceData, BaseTestCase):
    app_name = 'device_monitoring'
    model_name = 'DeviceData'
    data_model = DeviceData


@skipUnless(
    os.environ.get('SAMPLE_APP', False), 'Running tests on standard openwisp_monitoring'
)
class TestDeviceMonitoring(BaseTestDeviceMonitoring, BaseTestCase):
    app_name = 'device_monitoring'
    model_name = 'DeviceMonitoring'


@skipUnless(
    os.environ.get('SAMPLE_APP', False), 'Running tests on standard openwisp_monitoring'
)
class TestSettings(BaseTestSettings, DeviceMonitoringTestCase):
    app_name = 'device_monitoring'
