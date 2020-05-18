from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured

from . import DeviceMonitoringTestCase


class TestSettings(DeviceMonitoringTestCase):
    """
    Tests ``OpenWISP Device settings`` functionality
    """

    @patch(
        'django.conf.settings.OPENWISP_MONITORING_CRITICAL_DEVICE_METRICS',
        [{}],
        create=True,
    )
    def test_invalid_critical_device_metrics_setting(self):
        with self.assertRaises(ImproperlyConfigured):
            from ..settings import get_critical_device_metrics

            get_critical_device_metrics()

    @patch(
        'django.conf.settings.OPENWISP_MONITORING_HEALTH_STATUS_LABELS', {}, create=True
    )
    def test_invalid_health_status_setting(self):
        with self.assertRaises(ImproperlyConfigured):
            from ..settings import get_health_status_labels

            get_health_status_labels()
