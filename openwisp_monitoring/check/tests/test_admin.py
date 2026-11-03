from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory, TransactionTestCase, tag
from django.urls import reverse
from swapper import load_model

from ...device.tests import TestDeviceMonitoringMixin
from .. import settings as app_settings
from . import Device

Check = load_model("check", "Check")


@tag("flaky_with_udp_writes")
class TestAdmin(TestDeviceMonitoringMixin, TransactionTestCase):
    def _check_data(self, device, check=None):
        check_type = check.check_type if check else app_settings.CHECK_CLASSES[0][0]
        return {
            "name": check.name if check else "Test check",
            "is_active": "on",
            "description": "",
            "content_type": ContentType.objects.get_for_model(Device).pk,
            "object_id": str(device.pk),
            "check_type": check_type,
            "params": "{}",
        }

    def _post_check(self, device, check=None):
        if check:
            url = reverse(
                f"admin:{Check._meta.app_label}_{Check._meta.model_name}_change",
                args=[check.pk],
            )
        else:
            url = reverse(f"admin:{Check._meta.app_label}_{Check._meta.model_name}_add")
        return self.client.post(url, self._check_data(device, check))

    def test_check_admin_form_blocks_deactivated_device(self):
        source_device = self._create_device(
            organization=self._create_org(name="source org", slug="source-org")
        )
        check = Check.objects.filter(object_id=source_device.pk).first()
        device = self._create_device(
            name="blocked-device",
            mac_address="00:11:22:33:44:66",
            organization=self._get_org(),
        )
        device.deactivate()
        self.client.force_login(self._get_admin())
        for instance in (None, check):
            with self.subTest(instance=instance is not None):
                response = self._post_check(device, check=instance)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Monitoring is blocked")

    def test_check_admin_form_blocks_disabled_organization(self):
        source_device = self._create_device(
            organization=self._create_org(name="source org", slug="source-org")
        )
        check = Check.objects.filter(object_id=source_device.pk).first()
        organization = self._get_org()
        device = self._create_device(
            name="disabled-device",
            mac_address="00:11:22:33:44:66",
            organization=self._get_org(),
        )
        organization.is_active = False
        organization.save()
        self.client.force_login(self._get_admin())
        for instance in (None, check):
            with self.subTest(instance=instance is not None):
                response = self._post_check(device, check=instance)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Monitoring is blocked")

    def test_check_admin_form_allows_active_device(self):
        device = self._create_device(organization=self._create_org())
        self.client.force_login(self._get_admin())
        response = self._post_check(device)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            Check.objects.filter(object_id=device.pk, name="Test check").count(), 1
        )

    def test_check_admin_change_permission(self):
        d = self._create_device(organization=self._create_org())
        check = Check.objects.filter(object_id=d.pk).first()
        request = RequestFactory().get("/")
        request.user = self._get_admin()
        check_admin = admin.site._registry[Check]
        self.assertTrue(check_admin.has_change_permission(request, check))

    def test_check_admin_disabled_organization_read_only(self):
        org = self._create_org()
        d = self._create_device(organization=org)
        check = Check.objects.filter(object_id=d.pk).first()
        org.is_active = False
        org.save()
        request = RequestFactory().get("/")
        request.user = self._get_admin()
        check_admin = admin.site._registry[Check]
        self.assertFalse(check_admin.has_change_permission(request, check))
        self.assertTrue(check_admin.has_delete_permission(request, check))

    def test_check_admin_deactivated_device_read_only(self):
        d = self._create_device(organization=self._create_org())
        check = Check.objects.filter(object_id=d.pk).first()
        d.deactivate()
        request = RequestFactory().get("/")
        request.user = self._get_admin()
        check_admin = admin.site._registry[Check]
        self.assertFalse(check_admin.has_change_permission(request, check))
        self.assertTrue(check_admin.has_delete_permission(request, check))
