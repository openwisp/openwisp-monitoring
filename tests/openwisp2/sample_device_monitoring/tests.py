from openwisp_monitoring.device.models import DeviceData
from openwisp_monitoring.device.tests import DeviceMonitoringTestCase
from openwisp_monitoring.device.tests.test_models import BaseTestCase
from openwisp_monitoring.device.tests.test_models import (
    TestDeviceData as BaseTestDeviceData,
)
from openwisp_monitoring.device.tests.test_models import (
    TestDeviceMonitoring as BaseTestDeviceMonitoring,
)
from openwisp_monitoring.device.tests.test_recovery import (
    TestRecovery as BaseTestRecovery,
)
from openwisp_monitoring.device.tests.test_settings import (
    TestSettings as BaseTestSettings,
)


class TestRecovery(BaseTestRecovery, DeviceMonitoringTestCase):
    app_name = 'device_monitoring'


class TestDeviceData(BaseTestDeviceData, BaseTestCase):
    app_name = 'device_monitoring'
    model_name = 'DeviceData'
    data_model = DeviceData


class TestDeviceMonitoring(BaseTestDeviceMonitoring, BaseTestCase):
    app_name = 'device_monitoring'
    model_name = 'DeviceMonitoring'


class TestSettings(BaseTestSettings, DeviceMonitoringTestCase):
    app_name = 'device_monitoring'
