from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase
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


class TestAdmin(TestCase):
    def _login_admin(self):
        User = get_user_model()
        u = User.objects.create_superuser('admin', 'admin', 'test@test.com')
        self.client.force_login(u)
        return u

    def test_details_model_added(self):
        self._login_admin()
        r = self.client.get('/admin/')
        self.assertContains(r, '/admin/sample_check/detailsmodel/')
