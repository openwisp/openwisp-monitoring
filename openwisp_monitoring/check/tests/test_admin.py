from django.contrib import admin
from django.test import RequestFactory, TransactionTestCase, tag
from swapper import load_model

from ...device.tests import TestDeviceMonitoringMixin

Check = load_model("check", "Check")


@tag("flaky_with_udp_writes")
class TestAdmin(TestDeviceMonitoringMixin, TransactionTestCase):
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
