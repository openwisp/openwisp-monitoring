from openwisp_monitoring.monitoring.tests.test_charts import (
    TestCharts as BaseTestCharts,
)
from openwisp_monitoring.monitoring.tests.test_db_creation import (
    TestDatabase as BaseTestDatabase,
)
from openwisp_monitoring.monitoring.tests.test_models import (
    TestModels as BaseTestModels,
)
from openwisp_monitoring.monitoring.tests.test_monitoring_notifications import (
    TestMonitoringNotifications as BaseTestMonitoringNotifications,
)
from openwisp_monitoring.monitoring.tests.test_monitoring_notifications import (
    TestTransactionMonitoringNotifications as BaseTestTransactionMonitoringNotifications,
)


class TestDatabase(BaseTestDatabase):
    app = 'sample_monitoring'


class TestModels(BaseTestModels):
    def test_details_field(self):
        details = 'This metric has one related alert setting'
        m = self._create_object_metric(name='br-lan', details=details)
        self.assertEqual(m.details, details)
        alert_s = self._create_alert_settings(
            metric=m,
            custom_operator='>',
            custom_threshold=90,
            custom_tolerance=0,
            details=f'Related metric name is {m.name}',
        )
        self.assertEqual(alert_s.details, f'Related metric name is {m.name}')
        c = self._create_chart(metric=m)
        self.assertEqual(c.details, None)


class TestCharts(BaseTestCharts):
    pass


class TestMonitoringNotifications(BaseTestMonitoringNotifications):
    pass


class TestTransactionMonitoringNotifications(
    BaseTestTransactionMonitoringNotifications
):
    pass


# this is necessary to avoid excuting the base test suites
del BaseTestDatabase
del BaseTestCharts
del BaseTestModels
del BaseTestMonitoringNotifications
del BaseTestTransactionMonitoringNotifications
