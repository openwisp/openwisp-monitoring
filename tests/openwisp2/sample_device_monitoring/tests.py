from openwisp_monitoring.device.tests import (
    DeviceMonitoringTestCase as DeviceMonitoringTestCase,
)
from openwisp_monitoring.device.tests.test_admin import TestAdmin as BaseTestAdmin
from openwisp_monitoring.device.tests.test_admin import (
    TestWifiSessionAdmin as BaseTestWifiSessionAdmin,
)
from openwisp_monitoring.device.tests.test_api import TestDeviceApi as BaseTestDeviceApi
from openwisp_monitoring.device.tests.test_apps import TestApps as BaseTestApps
from openwisp_monitoring.device.tests.test_models import (
    TestDeviceData as BaseTestDeviceData,
)
from openwisp_monitoring.device.tests.test_models import (
    TestDeviceMonitoring as BaseTestDeviceMonitoring,
)
from openwisp_monitoring.device.tests.test_models import (
    TestWifiClientSession as BaseTestWifiClientSession,
)
from openwisp_monitoring.device.tests.test_recovery import (
    TestRecovery as BaseTestRecovery,
)
from openwisp_monitoring.device.tests.test_settings import (
    TestSettings as BaseTestSettings,
)
from openwisp_monitoring.device.tests.test_transactions import (
    TestTransactions as BaseTestTransactions,
)


class TestRecovery(BaseTestRecovery):
    pass


class TestDeviceData(BaseTestDeviceData):
    pass


class TestDeviceMonitoring(BaseTestDeviceMonitoring):
    def test_device_monitoring_str(self):
        d = self._create_device()
        dm = d.monitoring
        self.assertEqual(dm.details, 'devicemonitoring')
        self.assertEqual(str(dm), 'devicemonitoring')


class TestTransactions(BaseTestTransactions):
    pass


class TestSettings(BaseTestSettings):
    pass


class TestDeviceApi(BaseTestDeviceApi):
    pass


class TestAdmin(BaseTestAdmin):
    pass


class TestApps(BaseTestApps):
    pass


class TestWifiClientSession(BaseTestWifiClientSession):
    pass


class TestWifiSessionAdmin(BaseTestWifiSessionAdmin):
    pass


# this is necessary to avoid excuting the base test suites
del BaseTestRecovery
del DeviceMonitoringTestCase
del BaseTestDeviceData
del BaseTestDeviceMonitoring
del BaseTestTransactions
del BaseTestSettings
del BaseTestDeviceApi
del BaseTestAdmin
del BaseTestApps
del BaseTestWifiClientSession
del BaseTestWifiSessionAdmin
