from django.conf import settings

from ..settings import get_settings_value

CHECK_CLASSES = get_settings_value(
    'CHECK_CLASSES',
    (
        ('openwisp_monitoring.check.classes.Ping', 'Ping'),
        ('openwisp_monitoring.check.classes.ConfigApplied', 'Configuration Applied'),
        ('openwisp_monitoring.check.classes.Iperf3', 'Iperf3'),
    ),
)
AUTO_PING = get_settings_value('AUTO_PING', True)
AUTO_CONFIG_CHECK = get_settings_value('AUTO_DEVICE_CONFIG_CHECK', True)
# If OPENWISP_MONITORING_MANAGEMENT_IP_ONLY is not configured, use
# OPENWISP_CONTROLLER_MANAGEMENT_IP_ONLY.
MANAGEMENT_IP_ONLY = get_settings_value(
    'MANAGEMENT_IP_ONLY',
    getattr(settings, 'OPENWISP_CONTROLLER_MANAGEMENT_IP_ONLY', True),
)
PING_CHECK_CONFIG = get_settings_value('PING_CHECK_CONFIG', {})
AUTO_IPERF3 = get_settings_value('AUTO_IPERF3', False)
IPERF3_CHECK_CONFIG = get_settings_value('IPERF3_CHECK_CONFIG', {})
IPERF3_CHECK_LOCK_EXPIRE = get_settings_value(
    'IPERF3_CHECK_LOCK_EXPIRE', 10 * 60
)  # 10 minutes arbitrarily chosen (must be longer than TCP + UDP test time)
IPERF3_CHECK_DELETE_RSA_KEY = get_settings_value('IPERF3_CHECK_DELETE_RSA_KEY', True)
CHECKS_LIST = get_settings_value('CHECK_LIST', list(dict(CHECK_CLASSES).keys()))
CONFIG_CHECK_INTERVAL = int(
    get_settings_value('CONFIG_CHECK_INTERVAL', 5)
)  # in minutes
