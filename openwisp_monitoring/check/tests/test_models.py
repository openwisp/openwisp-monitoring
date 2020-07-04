from django.core.exceptions import ValidationError
from django.test import TransactionTestCase
from swapper import load_model

from ...device.tests import TestDeviceMonitoringMixin
from ..classes import Ping
from ..settings import CHECK_CLASSES

Check = load_model('check', 'Check')
Metric = load_model('monitoring', 'Metric')


class TestModels(TestDeviceMonitoringMixin, TransactionTestCase):
    _PING = CHECK_CLASSES[0][0]

    def test_check_str(self):
        c = Check(name='Test check')
        self.assertEqual(str(c), c.name)

    def test_check_no_content_type(self):
        c = Check(name='Ping class check', check=self._PING)
        m = c.check_instance._get_metric()
        self.assertEqual(m, Metric.objects.first())

    def test_check_str_with_relation(self):
        obj = self._create_user()
        c = Check(name='Check', content_object=obj)
        expected = '{0} (User: {1})'.format(c.name, obj)
        self.assertEqual(str(c), expected)

    def test_check_class(self):
        c = Check(name='Ping class check', check=self._PING)
        self.assertEqual(c.check_class, Ping)

    def test_base_check_class(self):
        path = 'openwisp_monitoring.check.classes.base.BaseCheck'
        c = Check(name='Base check', check=path)
        i = c.check_instance
        i.validate_params()
        with self.assertRaises(NotImplementedError):
            i.check()

    def test_check_instance(self):
        obj = self._create_device(organization=self._create_org())
        c = Check(
            name='Ping class check', check=self._PING, content_object=obj, params={}
        )
        i = c.check_instance
        self.assertIsInstance(i, Ping)
        self.assertEqual(i.related_object, obj)
        self.assertEqual(i.params, c.params)

    def test_validation(self):
        check = Check(name='Ping check', check=self._PING, params={})
        try:
            check.full_clean()
        except ValidationError as e:
            self.assertIn('device', str(e))
        else:
            self.fail('ValidationError not raised')

    def test_auto_ping(self):
        self.assertEqual(Check.objects.count(), 0)
        d = self._create_device(organization=self._create_org())
        self.assertEqual(Check.objects.count(), 1)
        c = Check.objects.first()
        self.assertEqual(c.content_object, d)
        self.assertIn('Ping', c.check)

    def test_device_deleted(self):
        self.assertEqual(Check.objects.count(), 0)
        d = self._create_device(organization=self._create_org())
        self.assertEqual(Check.objects.count(), 1)
        d.delete()
        self.assertEqual(Check.objects.count(), 0)
