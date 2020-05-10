from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured

from . import DeviceMonitoringTestCase


# TODO: The tests are validating correctly but coverage
# remains unaffected by them, figure out why?
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
        path = 'openwisp_monitoring/device/settings.py'
        with self.assertRaises(ImproperlyConfigured):
            exec(open(path).read())

    @patch(
        'django.conf.settings.OPENWISP_MONITORING_HEALTH_STATUS_LABELS', {}, create=True
    )
    def test_invalid_health_status_setting(self):
        path = 'openwisp_monitoring/device/settings.py'
        with self.assertRaises(ImproperlyConfigured):
            exec(open(path).read())
