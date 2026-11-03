from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from . import TestMonitoringMixin


class TestAdmin(TestMonitoringMixin, TestCase):
    app_label = "monitoring"
    check_app_label = "check"

    def _login_admin(self):
        User = get_user_model()
        u = User.objects.create_superuser("admin", "admin", "test@test.com")
        self.client.force_login(u)

    def test_metric_admin(self):
        m = self._create_general_metric()
        url = reverse(f"admin:{self.app_label}_metric_change", args=[m.pk])
        self._login_admin()
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

    def test_alert_settings_inline(self):
        m = self._create_general_metric(configuration="ping")
        alert_s = self._create_alert_settings(metric=m)
        self.assertIsNone(alert_s.custom_operator)
        self.assertIsNone(alert_s.custom_threshold)
        self.assertIsNone(alert_s.custom_tolerance)
        url = reverse(f"admin:{self.app_label}_metric_change", args=[m.pk])
        self._login_admin()

        with self.subTest("Test default values are shown as placeholders"):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, '<option value="&lt;" selected>less than</option>')
            self.assertContains(r, 'name="alertsettings-0-custom_threshold"')
            self.assertContains(r, 'placeholder="1"')
            self.assertNotContains(
                r, 'name="alertsettings-0-custom_threshold" value="1"'
            )
            self.assertContains(r, 'name="alertsettings-0-custom_tolerance"')
            self.assertContains(r, 'placeholder="30"')
            self.assertNotContains(
                r, 'name="alertsettings-0-custom_tolerance" value="30"'
            )

        with self.subTest("Test custom values are shown as input values"):
            alert_s.custom_operator = ">"
            alert_s.custom_threshold = 0.5
            alert_s.custom_tolerance = 15
            alert_s.save()
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            self.assertContains(
                r, '<option value="&gt;" selected>greater than</option>'
            )
            self.assertContains(
                r, 'name="alertsettings-0-custom_threshold" value="0.5"'
            )
            self.assertContains(r, 'placeholder="1"')
            self.assertContains(r, 'name="alertsettings-0-custom_tolerance" value="15"')
            self.assertContains(r, 'placeholder="30"')

    def test_admin_menu_groups(self):
        # Test menu group (openwisp-utils menu group) for Metric and Check models
        self._login_admin()
        response = self.client.get(reverse("admin:index"))
        with self.subTest("test menu group link for check model"):
            url = reverse(f"admin:{self.check_app_label}_check_changelist")
            self.assertContains(response, f'class="mg-link" href="{url}"')
        with self.subTest("test menu group link for metric model"):
            url = reverse(f"admin:{self.app_label}_metric_changelist")
            self.assertContains(response, f'class="mg-link" href="{url}"')
        with self.subTest('test "monitoring" group is registered'):
            self.assertContains(
                response,
                '<div class="mg-dropdown-label">Monitoring </div>',
                html=True,
            )
