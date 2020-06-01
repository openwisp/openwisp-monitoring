from openwisp_monitoring.monitoring.tests.test_charts import (
    TestCharts as BaseTestCharts,
)
from openwisp_monitoring.monitoring.tests.test_db_creation import (
    TestDatabase as BaseTestDatabase,
)
from openwisp_monitoring.monitoring.tests.test_models import (
    TestModels as BaseTestModels,
)


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


class TestCharts(BaseTestCharts):
    pass


# this is necessary to avoid excuting the base test suites
del BaseTestDatabase
del BaseTestCharts
del BaseTestModels
