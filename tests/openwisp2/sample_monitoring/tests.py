from django.contrib.auth import get_user_model
from django.test import TestCase
from openwisp_monitoring.monitoring.tests.test_graphs import (
    TestGraphs as BaseTestGraphs,
)
from openwisp_monitoring.monitoring.tests.test_models import (
    TestModels as BaseTestModels,
)
from swapper import load_model

Graph = load_model('monitoring', 'Graph')


class TestModels(BaseTestModels):
    pass


class TestGraphs(BaseTestGraphs):
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
        self.assertContains(r, '/admin/sample_monitoring/detailsmodel/')


del BaseTestGraphs
del BaseTestModels
