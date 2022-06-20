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
        # Some Public Iperf Servers : https://iperf.fr/iperf-servers.php#public-servers
        # 'be63c4e5-a68a-4650-bfe8-733837edb8be': ['iperf.biznetnetworks.com'],
        'a9734710-db30-46b0-a2fc-01f01046fe4f': ['speedtest.uztelecom.uz'],
        # '<org-pk>': ['<ORG_IPERF_SERVER>']
    },
)
