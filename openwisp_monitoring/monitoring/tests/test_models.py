import os
from unittest import skipIf

from django.test import TestCase

from ..base.tests.test_models import BaseTestModels
from . import TestMonitoringMixin


@skipIf(os.environ.get('SAMPLE_APP', False), 'Running tests on SAMPLE_APP')
class TestModels(BaseTestModels, TestMonitoringMixin, TestCase):
    app_name = 'monitoring'
    model_name = 'Metric'
