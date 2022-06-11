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
# By default it should be disabled.
AUTO_IPERF = get_settings_value('AUTO_IPERF', True)
IPERF_SERVERS = get_settings_value(
    'IPERF_SERVERS',
    {
        # Running on my local
        'be63c4e5-a68a-4650-bfe8-733837edb8be': ['192.168.5.109'],
        # '<org-pk>': ['<ORG_IPERF_SERVER>']
    },
)
