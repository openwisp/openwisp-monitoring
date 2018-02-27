from ...monitoring.tests import TestMonitoringMixin
from ..utils import manage_short_retention_policy


class TestDeviceMonitoringMixin(TestMonitoringMixin):
    @classmethod
    def setUpClass(cls):
        super(TestDeviceMonitoringMixin, cls).setUpClass()
        manage_short_retention_policy()
