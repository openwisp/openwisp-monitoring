import json

from django.core.exceptions import ValidationError
from django.test import TestCase

from openwisp_controller.config.models import Config, Device
from openwisp_controller.config.tests import CreateConfigTemplateMixin
from openwisp_users.tests.utils import TestOrganizationMixin

from ..models import DeviceDynamicData


class TestModels(TestOrganizationMixin,
                 CreateConfigTemplateMixin,
                 TestCase):
    """
    Test openwisp_monitoring.device.models
    """
    device_model = Device
    config_model = Config

    def _create_device(self, **kwargs):
        if 'organization' not in kwargs:
            kwargs['organization'] = self._create_org()
        return super(TestModels, self)._create_device(**kwargs)

    def test_clean_data_ok(self):
        d = self._create_device()
        ddd = DeviceDynamicData(device=d)
        ddd.data = {'interfaces': []}
        ddd.full_clean()

    def test_clean_data_fail(self):
        d = self._create_device()
        ddd = DeviceDynamicData(device=d)
        try:
            ddd.data = {'interfaces': [{}]}
            ddd.full_clean()
        except ValidationError as e:
            self.assertIn('data', e.message_dict)
            self.assertIn('Invalid data in',
                          str(e.message_dict['data']))
            self.assertIn('"#/interfaces/0"',
                          str(e.message_dict['data']))
        else:
            self.fail('ValidationError not raised')

    def test_json(self):
        d = self._create_device()
        ddd = DeviceDynamicData(device=d)
        ddd.data = {'interfaces': []}
        try:
            json.loads(ddd.json(indent=True))
        except Exception as e:
            self.fail('json method did not return valid JSON')
