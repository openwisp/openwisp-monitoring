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

    def test_alert_settings_inline(self):
        m = self._create_general_metric(configuration='ping')
        alert_s = self._create_alert_settings(metric=m)
        self.assertIsNone(alert_s.custom_operator)
        self.assertIsNone(alert_s.custom_threshold)
        self.assertIsNone(alert_s.custom_tolerance)
        url = reverse('admin:monitoring_metric_change', args=[m.pk])
        self._login_admin()
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, '<option value="&lt;" selected>less than</option>')
        self.assertContains(r, 'name="alertsettings-0-custom_threshold" value="1"')
        self.assertContains(r, 'name="alertsettings-0-custom_tolerance" value="0"')

    def test_admin_menu_groups(self):
        # Test menu group (openwisp-utils menu group) for Metric and Check models
        self._login_admin()
        response = self.client.get(reverse('admin:index'))
        with self.subTest('test menu group link for check model'):
            url = reverse('admin:check_check_changelist')
            self.assertContains(response, f'class="mg-link" href="{url}"')
        with self.subTest('test menu group link for metric model'):
            url = reverse('admin:monitoring_metric_changelist')
            self.assertContains(response, f'class="mg-link" href="{url}"')
        with self.subTest('test "monitoring" group is registered'):
            self.assertContains(
                response,
                '<div class="mg-dropdown-label">Monitoring </div>',
                html=True,
            )
