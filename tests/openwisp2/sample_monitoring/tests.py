import os
from unittest import skipUnless

from django.test import TestCase
from openwisp_monitoring.monitoring.base.tests.test_graphs import BaseTestGraphs
from openwisp_monitoring.monitoring.base.tests.test_models import BaseTestModels
from openwisp_monitoring.monitoring.tests import TestMonitoringMixin
from swapper import load_model

Graph = load_model('monitoring', 'Graph')


@skipUnless(
    os.environ.get('SAMPLE_APP', False), 'Running tests on standard openwisp_monitoring'
)
class TestModels(BaseTestModels, TestMonitoringMixin, TestCase):
    app_name = 'openwisp2.sample_monitoring'
    model_name = 'Metric'


@skipUnless(
    os.environ.get('SAMPLE_APP', False), 'Running tests on standard openwisp_monitoring'
)
class TestGraphs(BaseTestGraphs, TestMonitoringMixin, TestCase):
    app_name = 'openwisp2.sample_monitoring'
    graph_model = Graph
