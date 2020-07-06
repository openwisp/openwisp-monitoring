from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from . import TestMonitoringMixin


class TestAdmin(TestMonitoringMixin, TestCase):

    def _login_admin(self):
        User = get_user_model()
        u = User.objects.create_superuser('admin', 'admin', 'test@test.com')
        self.client.force_login(u)

    def test_metric_admin(self):
        m = self._create_general_metric()
        url = reverse('admin:monitoring_metric_change', args=[m.pk])
        self._login_admin()
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
