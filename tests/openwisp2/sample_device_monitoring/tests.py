import os
from unittest import skipUnless

from openwisp_monitoring.device.base.tests.test_api import BaseTestDeviceApi
from openwisp_monitoring.device.base.tests.test_models import (
    BaseTestCase,
    BaseTestDeviceData,
    BaseTestDeviceMonitoring,
)
from openwisp_monitoring.device.base.tests.test_recovery import BaseTestRecovery
from openwisp_monitoring.device.base.tests.test_settings import BaseTestSettings
from openwisp_monitoring.device.tests import DeviceMonitoringTestCase
from swapper import load_model

DeviceData = load_model('sample_device_monitoring', 'DeviceData')


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
class TestDeviceApi(BaseTestDeviceApi, DeviceMonitoringTestCase):
    app_name = 'device_monitoring'
    model_name = 'DeviceData'
    data_model = DeviceData


@skipUnless(
    os.environ.get('SAMPLE_APP', False), 'Running tests on standard openwisp_monitoring'
)
class TestSettings(BaseTestSettings, DeviceMonitoringTestCase):
    app_name = 'device_monitoring'
