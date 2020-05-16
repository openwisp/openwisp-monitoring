import os
from unittest import skipIf

from ..base.tests.test_models import (
    BaseTestCase,
    BaseTestDeviceData,
    BaseTestDeviceMonitoring,
)
from ..models import DeviceData


@skipIf(os.environ.get('SAMPLE_APP', False), 'Running tests on SAMPLE_APP')
class TestDeviceData(BaseTestDeviceData, BaseTestCase):
    app_name = 'device_monitoring'
    model_name = 'DeviceData'
    data_model = DeviceData


@skipIf(os.environ.get('SAMPLE_APP', False), 'Running tests on SAMPLE_APP')
class TestDeviceMonitoring(BaseTestDeviceMonitoring, BaseTestCase):
    app_name = 'device_monitoring'
    model_name = 'DeviceMonitoring'
