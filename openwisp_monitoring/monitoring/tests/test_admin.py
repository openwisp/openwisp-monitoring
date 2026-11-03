from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory, TestCase
from django.urls import reverse
from swapper import load_model

from ...device.tests import TestDeviceMonitoringMixin

Metric = load_model("monitoring", "Metric")


class TestAdmin(TestDeviceMonitoringMixin, TestCase):
    app_label = "monitoring"
    check_app_label = "check"

    def _login_admin(self):
        User = get_user_model()
        u = User.objects.create_superuser("admin", "admin", "test@test.com")
        self.client.force_login(u)

    def _metric_data(self, device, metric=None):
        data = {
            "name": metric.name if metric else "Test metric",
            "key": "",
            "field_name": "",
            "configuration": metric.configuration if metric else "test_metric",
            "content_type": ContentType.objects.get_for_model(device).pk,
            "object_id": str(device.pk),
            "main_tags": "{}",
            "extra_tags": "{}",
        }
        for prefix in ("chart_set", "alertsettings"):
            data.update(
                {
                    f"{prefix}-TOTAL_FORMS": "0",
                    f"{prefix}-INITIAL_FORMS": "0",
                    f"{prefix}-MIN_NUM_FORMS": "0",
                    f"{prefix}-MAX_NUM_FORMS": "1000",
                }
            )
        return data

    def _post_metric(self, device, metric=None):
        if metric:
            url = reverse(
                f"admin:{Metric._meta.app_label}_{Metric._meta.model_name}_change",
                args=[metric.pk],
            )
        else:
            url = reverse(
                f"admin:{Metric._meta.app_label}_{Metric._meta.model_name}_add"
            )
        return self.client.post(url, self._metric_data(device, metric))

    def test_metric_admin_form_blocks_deactivated_device(self):
        source_device = self._create_device(
            organization=self._create_org(name="source org", slug="source-org")
        )
        metric = self._create_object_metric(content_object=source_device)
        device = self._create_device(
            name="blocked-device",
            mac_address="00:11:22:33:44:66",
            organization=self._get_org(),
        )
        device.deactivate()
        self._login_admin()
        for instance in (None, metric):
            with self.subTest(instance=instance is not None):
                response = self._post_metric(device, metric=instance)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Monitoring is blocked")

    def test_metric_admin_form_blocks_disabled_organization(self):
        source_device = self._create_device(
            organization=self._create_org(name="source org", slug="source-org")
        )
        metric = self._create_object_metric(content_object=source_device)
        organization = self._get_org()
        device = self._create_device(
            name="disabled-device",
            mac_address="00:11:22:33:44:66",
            organization=self._get_org(),
        )
        organization.is_active = False
        organization.save()
        self._login_admin()
        for instance in (None, metric):
            with self.subTest(instance=instance is not None):
                response = self._post_metric(device, metric=instance)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Monitoring is blocked")

    def test_metric_admin_form_allows_active_device(self):
        device = self._create_device(organization=self._create_org())
        metric = self._create_object_metric(content_object=device)
        self._login_admin()
        response = self._post_metric(device, metric)
        self.assertEqual(
            response.status_code,
            302,
            response.content.decode(),
        )

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
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, '<option value="&lt;" selected>less than</option>')
        self.assertContains(r, 'name="alertsettings-0-custom_threshold" value="1"')
        self.assertContains(r, 'name="alertsettings-0-custom_tolerance" value="30"')

    def test_metric_admin_disabled_organization_read_only(self):
        device = self._create_device(organization=self._create_org(is_active=False))
        metric = self._create_object_metric(content_object=device)
        self._create_alert_settings(metric=metric)
        request = RequestFactory().get("/")
        request.user = self._get_admin()
        metric_admin = admin.site._registry[Metric]
        self.assertFalse(metric_admin.has_change_permission(request, metric))
        self.assertTrue(metric_admin.has_delete_permission(request, metric))
        for inline_class in metric_admin.inlines:
            with self.subTest(inline=inline_class.__name__):
                inline = inline_class(Metric, admin.site)
                self.assertFalse(inline.has_add_permission(request, metric))
                self.assertFalse(inline.has_change_permission(request, metric))
                self.assertTrue(inline.has_delete_permission(request, metric))

    def test_metric_admin_deactivated_device_read_only(self):
        device = self._create_device(organization=self._create_org())
        device.deactivate()
        metric = self._create_object_metric(content_object=device)
        self._create_alert_settings(metric=metric)
        request = RequestFactory().get("/")
        request.user = self._get_admin()
        metric_admin = admin.site._registry[Metric]
        self.assertFalse(metric_admin.has_change_permission(request, metric))
        self.assertTrue(metric_admin.has_delete_permission(request, metric))
        for inline_class in metric_admin.inlines:
            with self.subTest(inline=inline_class.__name__):
                inline = inline_class(Metric, admin.site)
                self.assertFalse(inline.has_add_permission(request, metric))
                self.assertFalse(inline.has_change_permission(request, metric))
                self.assertTrue(inline.has_delete_permission(request, metric))

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
