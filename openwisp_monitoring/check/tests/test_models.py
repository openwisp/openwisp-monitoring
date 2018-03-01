from django.test import TestCase

from ...monitoring.tests import TestMonitoringMixin
from ..classes import Ping
from ..models import Check
from ..settings import CHECK_CLASSES


class TestModels(TestMonitoringMixin, TestCase):
    _PING = CHECK_CLASSES[0][0]

    def test_check_str(self):
        c = Check(name='Test check')
        self.assertEqual(str(c), c.name)

    def test_check_str_with_relation(self):
        obj = self._create_user()
        c = Check(name='Check', content_object=obj)
        expected = '{0} (User: {1})'.format(c.name, obj)
        self.assertEqual(str(c), expected)

    def test_check_class(self):
        c = Check(name='Ping class check', check=self._PING)
        self.assertEqual(c.check_class, Ping)

    def test_check_instance(self):
        obj = self._create_user()
        c = Check(name='Ping class check',
                  check=self._PING,
                  content_object=obj,
                  params={'test': 'test'})
        i = c.check_instance
        self.assertIsInstance(i, Ping)
        self.assertEqual(i.instance, obj)
        self.assertEqual(i.params, c.params)
