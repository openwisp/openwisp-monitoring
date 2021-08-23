from ..settings import get_settings_value

CHECK_CLASSES = get_settings_value(
    'CHECK_CLASSES',
    (
        ('openwisp_monitoring.check.classes.Ping', 'Ping'),
        ('openwisp_monitoring.check.classes.ConfigApplied', 'Configuration Applied'),
        ('openwisp_monitoring.check.classes.Snmp', 'SNMP Device Monitoring',),
    ),
)
AUTO_PING = get_settings_value('AUTO_PING', True)
AUTO_CONFIG_CHECK = get_settings_value('AUTO_DEVICE_CONFIG_CHECK', True)
AUTO_SNMP = get_settings_value('AUTO_SNMP', False)
MANAGEMENT_IP_ONLY = get_settings_value('MANAGEMENT_IP_ONLY', True)
