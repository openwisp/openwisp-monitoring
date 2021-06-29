from ..settings import get_settings_value

CHECK_CLASSES = get_settings_value(
    'CHECK_CLASSES',
    (
        ('openwisp_monitoring.check.classes.Ping', 'Ping'),
        ('openwisp_monitoring.check.classes.ConfigApplied', 'Configuration Applied'),
        (
            'openwisp_monitoring.check.classes.SnmpDeviceMonitoring',
            'SNMP Device Monitoring',
        ),
    ),
)
AUTO_PING = getattr(settings, 'OPENWISP_MONITORING_AUTO_PING', True)
AUTO_SNMP_DEVICEMONITORING = getattr(
    settings, 'OPENWISP_MONITORING_AUTO_SNMP_DEVICEMONITORING', True
)
AUTO_CONFIG_CHECK = getattr(
    settings, 'OPENWISP_MONITORING_AUTO_DEVICE_CONFIG_CHECK', True
)
MANAGEMENT_IP_ONLY = getattr(settings, 'OPENWISP_MONITORING_MANAGEMENT_IP_ONLY', True)
