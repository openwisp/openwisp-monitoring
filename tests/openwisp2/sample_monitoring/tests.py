from django.test import TestCase
from openwisp_monitoring.monitoring.tests import TestMonitoringMixin
from openwisp_monitoring.monitoring.tests.test_graphs import (
    TestGraphs as BaseTestGraphs,
)
from openwisp_monitoring.monitoring.tests.test_models import (
    TestModels as BaseTestModels,
)
from swapper import load_model

Graph = load_model('monitoring', 'Graph')


class TestModels(BaseTestModels, TestMonitoringMixin, TestCase):
    app_name = 'openwisp2.sample_monitoring'
    model_name = 'Metric'


class TestGraphs(BaseTestGraphs, TestMonitoringMixin, TestCase):
    app_name = 'openwisp2.sample_monitoring'
    graph_model = Graph
