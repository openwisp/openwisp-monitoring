from ..settings import get_settings_value

CHECK_CLASSES = get_settings_value(
    'CHECK_CLASSES',
    (
        ('openwisp_monitoring.check.classes.Ping', 'Ping'),
        ('openwisp_monitoring.check.classes.ConfigApplied', 'Configuration Applied'),
        ('openwisp_monitoring.check.classes.Iperf', 'Iperf'),
    ),
)
AUTO_PING = get_settings_value('AUTO_PING', True)
AUTO_CONFIG_CHECK = get_settings_value('AUTO_DEVICE_CONFIG_CHECK', True)
MANAGEMENT_IP_ONLY = get_settings_value('MANAGEMENT_IP_ONLY', True)
PING_CHECK_CONFIG = get_settings_value('PING_CHECK_CONFIG', {})
AUTO_IPERF = get_settings_value('AUTO_IPERF', False)
IPERF_SERVERS = get_settings_value('IPERF_SERVERS', {})
