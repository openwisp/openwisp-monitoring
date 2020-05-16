import os
from unittest import skipIf

from django.test import TestCase

from ..base.tests.test_graphs import BaseTestGraphs
from ..models import Graph
from . import TestMonitoringMixin


@skipIf(os.environ.get('SAMPLE_APP', False), 'Running tests on SAMPLE_APP')
class TestGraphs(TestMonitoringMixin, BaseTestGraphs, TestCase):
    app_label = 'monitoring'
    graph_model = Graph
