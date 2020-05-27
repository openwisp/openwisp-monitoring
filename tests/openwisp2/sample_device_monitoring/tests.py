from django.contrib.auth import get_user_model
from django.test import TestCase
from openwisp_monitoring.device.tests import (
    DeviceMonitoringTestCase as DeviceMonitoringTestCase,
)
from openwisp_monitoring.device.tests.test_api import TestDeviceApi as BaseTestDeviceApi
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


class TestRecovery(BaseTestRecovery):
    pass


class TestDeviceData(BaseTestDeviceData):
    pass


class TestDeviceMonitoring(BaseTestDeviceMonitoring):
    pass


class TestSettings(BaseTestSettings):
    pass


class TestAdmin(TestCase):
    def _login_admin(self):
        User = get_user_model()
        u = User.objects.create_superuser('admin', 'admin', 'test@test.com')
        self.client.force_login(u)
        return u

    def test_details_model_added(self):
        self._login_admin()
        r = self.client.get('/admin/')
        self.assertContains(r, '/admin/sample_device_monitoring/detailsmodel/')


class TestDeviceApi(BaseTestDeviceApi):
    pass


del BaseTestRecovery
del DeviceMonitoringTestCase
del BaseTestDeviceData
del BaseTestDeviceMonitoring
del TestAdmin
del BaseTestSettings
del BaseTestDeviceApi
