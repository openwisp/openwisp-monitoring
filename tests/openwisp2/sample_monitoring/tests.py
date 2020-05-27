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
    pass


class TestGraphs(BaseTestGraphs):
    pass


# this is necessary to avoid excuting the base test suites
del BaseTestDatabase
del BaseTestGraphs
del BaseTestModels
