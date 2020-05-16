import os
from unittest import skipIf

from ..base.tests.test_api import BaseTestDeviceApi
from ..models import DeviceData
from . import DeviceMonitoringTestCase


@skipIf(os.environ.get('SAMPLE_APP', False), 'Running tests on SAMPLE_APP')
class TestDeviceApi(BaseTestDeviceApi, DeviceMonitoringTestCase):
    app_name = 'device_monitoring'
    model_name = 'DeviceData'
    data_model = DeviceData
