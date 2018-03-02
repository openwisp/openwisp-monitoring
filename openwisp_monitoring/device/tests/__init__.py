from ...monitoring.tests import TestMonitoringMixin
from ..utils import manage_short_retention_policy

from django.test import TestCase

from openwisp_controller.config.models import Config, Device
from openwisp_controller.config.tests import CreateConfigTemplateMixin


class TestDeviceMonitoringMixin(CreateConfigTemplateMixin,
                                TestMonitoringMixin,
                                TestCase):
    device_model = Device
    config_model = Config

    @classmethod
    def setUpClass(cls):
        super(TestDeviceMonitoringMixin, cls).setUpClass()
        manage_short_retention_policy()
