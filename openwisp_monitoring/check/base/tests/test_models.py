from django.core.exceptions import ValidationError
from openwisp_monitoring.check.classes import Ping
from openwisp_monitoring.check.settings import CHECK_CLASSES


class BaseTestModels(object):
    _PING = CHECK_CLASSES[0][0]

    def test_check_str(self):
        c = self.check_model(name='Test check')
        self.assertEqual(str(c), c.name)

    def test_check_str_with_relation(self):
        obj = self._create_user()
        c = self.check_model(name='Check', content_object=obj)
        expected = '{0} (User: {1})'.format(c.name, obj)
        self.assertEqual(str(c), expected)

    def test_check_class(self):
        c = self.check_model(name='Ping class check', check=self._PING)
        self.assertEqual(c.check_class, Ping)

    def test_check_instance(self):
        obj = self._create_device(organization=self._create_org())
        c = self.check_model(
            name='Ping class check', check=self._PING, content_object=obj, params={}
        )
        i = c.check_instance
        self.assertIsInstance(i, Ping)
        self.assertEqual(i.related_object, obj)
        self.assertEqual(i.params, c.params)

    def test_validation(self):
        check = self.check_model(name='Ping check', check=self._PING, params={})
        try:
            check.full_clean()
        except ValidationError as e:
            self.assertIn('device', str(e))
        else:
            self.fail('ValidationError not raised')

    def test_auto_ping(self):
        self.assertEqual(self.check_model.objects.count(), 0)
        d = self._create_device(organization=self._create_org())
        self.assertEqual(self.check_model.objects.count(), 1)
        c = self.check_model.objects.first()
        self.assertEqual(c.content_object, d)
        self.assertIn('Ping', c.check)

    def test_device_deleted(self):
        self.assertEqual(self.check_model.objects.count(), 0)
        d = self._create_device(organization=self._create_org())
        self.assertEqual(self.check_model.objects.count(), 1)
        d.delete()
        self.assertEqual(self.check_model.objects.count(), 0)
