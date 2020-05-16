import os
from unittest import skipIf

from django.test import TransactionTestCase
from openwisp_monitoring.device.tests import TestDeviceMonitoringMixin

from ..base.tests.test_ping import BaseTestPing
from ..models import Check


@skipIf(os.environ.get('SAMPLE_APP', False), 'Running tests on SAMPLE_APP')
class TestPing(BaseTestPing, TestDeviceMonitoringMixin, TransactionTestCase):
    app_label = 'check'
    check_model = Check
