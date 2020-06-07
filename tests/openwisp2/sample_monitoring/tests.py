from openwisp_monitoring.monitoring.tests.test_db_creation import (
    TestDatabase as BaseTestDatabase,
)
from openwisp_monitoring.monitoring.tests.test_graphs import (
    TestGraphs as BaseTestGraphs,
)
from openwisp_monitoring.monitoring.tests.test_models import (
    TestModels as BaseTestModels,
)
from swapper import load_model

Graph = load_model('monitoring', 'Graph')


class TestDatabase(BaseTestDatabase):
    app = 'sample_monitoring'


class TestModels(BaseTestModels):
    def test_details_field(self):
        details = 'This metric has one related threshold'
        m = self._create_object_metric(name='br-lan', details=details)
        self.assertEqual(m.details, details)
        t = self._create_threshold(
            metric=m,
            operator='>',
            value=90,
            seconds=0,
            details=f'Related metric name is {m.name}',
        )
        self.assertEqual(t.details, f'Related metric name is {m.name}')
        g = self._create_graph(metric=m)
        self.assertEqual(g.details, None)


class TestGraphs(BaseTestGraphs):
    pass


# this is necessary to avoid excuting the base test suites
del BaseTestDatabase
del BaseTestGraphs
del BaseTestModels
