from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TransactionTestCase
from django.utils.timezone import now
from freezegun import freeze_time
from swapper import load_model

from ...device.tests import TestDeviceMonitoringMixin
from .. import settings as app_settings
from ..classes import ConfigApplied, Ping
from ..tasks import auto_create_config_check, auto_create_ping

Check = load_model('check', 'Check')
Metric = load_model('monitoring', 'Metric')
AlertSettings = load_model('monitoring', 'AlertSettings')
Device = load_model('config', 'device')
Notification = load_model('openwisp_notifications', 'Notification')


class TestModels(TestDeviceMonitoringMixin, TransactionTestCase):
    _PING = app_settings.CHECK_CLASSES[0][0]
    _CONFIG_APPLIED = app_settings.CHECK_CLASSES[1][0]

    def test_check_str(self):
        c = Check(name='Test check')
        self.assertEqual(str(c), c.name)

    def test_check_no_content_type(self):
        c = Check(name='Ping class check', check_type=self._PING)
        m = c.check_instance._get_metric()
        self.assertEqual(m, Metric.objects.first())

    def test_check_str_with_relation(self):
        obj = self._create_user()
        c = Check(name='Check', content_object=obj)
        expected = '{0} (User: {1})'.format(c.name, obj)
        self.assertEqual(str(c), expected)

    def test_check_class(self):
        with self.subTest('Test Ping check Class'):
            c = Check(name='Ping class check', check_type=self._PING)
            self.assertEqual(c.check_class, Ping)
        with self.subTest('Test Configuration Applied check Class'):
            c = Check(
                name='Configuration Applied class check',
                check_type=self._CONFIG_APPLIED,
            )
            self.assertEqual(c.check_class, ConfigApplied)

    def test_base_check_class(self):
        path = 'openwisp_monitoring.check.classes.base.BaseCheck'
        c = Check(name='Base check', check_type=path)
        i = c.check_instance
        i.validate_params()
        with self.assertRaises(NotImplementedError):
            i.check()

    def test_check_instance(self):
        obj = self._create_device(organization=self._create_org())
        with self.subTest('Test Ping check instance'):
            c = Check(
                name='Ping class check',
                check_type=self._PING,
                content_object=obj,
                params={},
            )
            i = c.check_instance
            self.assertIsInstance(i, Ping)
            self.assertEqual(i.related_object, obj)
            self.assertEqual(i.params, c.params)
        with self.subTest('Test Configuration Applied check instance'):
            c = Check(
                name='Configuration Applied class check',
                check_type=self._CONFIG_APPLIED,
                content_object=obj,
                params={},
            )
            i = c.check_instance
            self.assertIsInstance(i, ConfigApplied)
            self.assertEqual(i.related_object, obj)
            self.assertEqual(i.params, c.params)

    def test_validation(self):
        with self.subTest('Test Ping check validation'):
            check = Check(name='Ping check', check_type=self._PING, params={})
            try:
                check.full_clean()
            except ValidationError as e:
                self.assertIn('device', str(e))
            else:
                self.fail('ValidationError not raised')
        with self.subTest('Test Configuration Applied check validation'):
            check = Check(
                name='Config check', check_type=self._CONFIG_APPLIED, params={}
            )
            try:
                check.full_clean()
            except ValidationError as e:
                self.assertIn('device', str(e))
            else:
                self.fail('ValidationError not raised')

    def test_auto_check_creation(self):
        self.assertEqual(Check.objects.count(), 0)
        d = self._create_device(organization=self._create_org())
        self.assertEqual(Check.objects.count(), 2)
        with self.subTest('Test AUTO_PING'):
            c1 = Check.objects.filter(check_type=self._PING).first()
            self.assertEqual(c1.content_object, d)
            self.assertEqual(self._PING, c1.check_type)
        with self.subTest('Test AUTO_CONFIG_CHECK'):
            c2 = Check.objects.filter(check_type=self._CONFIG_APPLIED).first()
            self.assertEqual(c2.content_object, d)
            self.assertEqual(self._CONFIG_APPLIED, c2.check_type)

    def test_device_deleted(self):
        self.assertEqual(Check.objects.count(), 0)
        d = self._create_device(organization=self._create_org())
        self.assertEqual(Check.objects.count(), 2)
        d.delete()
        self.assertEqual(Check.objects.count(), 0)

    @patch('openwisp_monitoring.check.settings.AUTO_PING', False)
    def test_config_modified_device_problem(self):
        self._create_admin()
        self.assertEqual(Check.objects.count(), 0)
        self._create_config(status='modified', organization=self._create_org())
        d = Device.objects.first()
        d.monitoring.update_status('ok')
        self.assertEqual(Check.objects.count(), 2)
        self.assertEqual(Metric.objects.count(), 0)
        self.assertEqual(AlertSettings.objects.count(), 0)
        check = Check.objects.filter(check_type=self._CONFIG_APPLIED).first()
        with freeze_time(now() - timedelta(minutes=10)):
            check.perform_check()
        self.assertEqual(Metric.objects.count(), 1)
        self.assertEqual(AlertSettings.objects.count(), 1)
        # Check needs to be run again without mocking time for threshold crossed
        check.perform_check()
        m = Metric.objects.first()
        self.assertEqual(m.content_object, d)
        self.assertEqual(m.key, 'config_applied')
        dm = d.monitoring
        dm.refresh_from_db()
        self.assertEqual(m.is_healthy, False)
        self.assertEqual(m.is_healthy_tolerant, False)
        self.assertEqual(dm.status, 'problem')
        self.assertEqual(Notification.objects.count(), 1)

    @patch('openwisp_monitoring.check.settings.AUTO_PING', False)
    def test_config_error(self):
        """
        Test that ConfigApplied checks are skipped when device config status is errored
        """
        self._create_admin()
        self.assertEqual(Check.objects.count(), 0)
        self._create_config(status='error', organization=self._create_org())
        dm = Device.objects.first().monitoring
        dm.update_status('ok')
        self.assertEqual(Check.objects.count(), 2)
        self.assertEqual(Metric.objects.count(), 0)
        self.assertEqual(AlertSettings.objects.count(), 0)
        check = Check.objects.filter(check_type=self._CONFIG_APPLIED).first()
        with freeze_time(now() - timedelta(minutes=10)):
            check.perform_check()
        # Check needs to be run again without mocking time for threshold crossed
        self.assertEqual(check.perform_check(), 0)
        self.assertEqual(Metric.objects.count(), 1)
        m = Metric.objects.first()
        self.assertEqual(AlertSettings.objects.count(), 1)
        dm.refresh_from_db()
        self.assertEqual(dm.status, 'problem')
        self.assertEqual(Notification.objects.filter(actor_object_id=m.id).count(), 0)
        # Check config recovery
        dm.device.config.set_status_applied()
        # We are once again querying for the check to override the cached property check_instance
        check = Check.objects.filter(check_type=self._CONFIG_APPLIED).first()
        # must be performed multiple times to trepass tolerance
        check.perform_check()
        with freeze_time(now() + timedelta(minutes=10)):
            check.perform_check()
        dm.refresh_from_db()
        self.assertEqual(dm.status, 'ok')
        self.assertEqual(Notification.objects.filter(actor_object_id=m.id).count(), 1)

    @patch(
        'openwisp_monitoring.device.base.models.app_settings.CRITICAL_DEVICE_METRICS',
        [{'key': 'config_applied', 'field_name': 'config_applied'}],
    )
    @patch('openwisp_monitoring.check.settings.AUTO_PING', False)
    def test_config_check_critical_metric(self):
        self._create_config(status='modified', organization=self._create_org())
        self.assertEqual(Check.objects.count(), 2)
        d = Device.objects.first()
        dm = d.monitoring
        dm.update_status('ok')
        check = Check.objects.filter(check_type=self._CONFIG_APPLIED).first()
        check.perform_check()
        self.assertEqual(Metric.objects.count(), 1)
        self.assertEqual(AlertSettings.objects.count(), 1)
        m = Metric.objects.first()
        self.assertTrue(dm.is_metric_critical(m))
        # must be executed twice to trepass the tolerance
        with freeze_time(now() - timedelta(minutes=6)):
            check.perform_check()
        check.perform_check()
        dm.refresh_from_db()
        self.assertEqual(dm.status, 'critical')

    def test_no_duplicate_check_created(self):
        self._create_config(organization=self._create_org())
        self.assertEqual(Check.objects.count(), 2)
        d = Device.objects.first()
        auto_create_config_check.delay(
            model=Device.__name__.lower(),
            app_label=Device._meta.app_label,
            object_id=str(d.pk),
        )
        auto_create_ping.delay(
            model=Device.__name__.lower(),
            app_label=Device._meta.app_label,
            object_id=str(d.pk),
        )
        self.assertEqual(Check.objects.count(), 2)

    def test_device_unreachable_no_config_check(self):
        self._create_config(status='modified', organization=self._create_org())
        d = self.device_model.objects.first()
        d.monitoring.update_status('critical')
        self.assertEqual(Check.objects.count(), 2)
        c2 = Check.objects.filter(check_type=self._CONFIG_APPLIED).first()
        c2.perform_check()
        self.assertEqual(Metric.objects.count(), 0)
        self.assertIsNone(c2.perform_check())

    def test_device_unknown_no_config_check(self):
        self._create_admin()
        self._create_config(status='modified', organization=self._create_org())
        d = self.device_model.objects.first()
        d.monitoring.update_status('unknown')
        self.assertEqual(Check.objects.count(), 2)
        c2 = Check.objects.filter(check_type=self._CONFIG_APPLIED).first()
        c2.perform_check()
        self.assertEqual(Metric.objects.count(), 0)
        self.assertEqual(Notification.objects.count(), 0)
        self.assertIsNone(c2.perform_check())
