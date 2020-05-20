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
    pass


class TestDeviceData(BaseTestDeviceData, BaseTestCase):
    pass


class TestDeviceMonitoring(BaseTestDeviceMonitoring, BaseTestCase):
    pass


class TestSettings(BaseTestSettings, DeviceMonitoringTestCase):
    pass
