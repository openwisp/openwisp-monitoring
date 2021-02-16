from django.conf import settings

CHECK_CLASSES = getattr(
    settings,
    'OPENWISP_MONITORING_CHECK_CLASSES',
    (
        ('openwisp_monitoring.check.classes.Ping', 'Ping'),
        ('openwisp_monitoring.check.classes.ConfigApplied', 'Configuration Applied'),
    ),
)
AUTO_PING = getattr(settings, 'OPENWISP_MONITORING_AUTO_PING', True)
AUTO_CONFIG_CHECK = getattr(
    settings, 'OPENWISP_MONITORING_AUTO_DEVICE_CONFIG_CHECK', True
)
MANAGEMENT_IP_ONLY = getattr(settings, 'OPENWISP_MONITORING_MANAGEMENT_IP_ONLY', True)
