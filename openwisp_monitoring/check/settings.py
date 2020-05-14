from django.conf import settings

CHECK_CLASSES = getattr(
    settings,
    'OPENWISP_MONITORING_CHECK_CLASSES',
    (('openwisp_monitoring.check.classes.Ping', 'Ping'),),
)
AUTO_PING = getattr(settings, 'OPENWISP_MONITORING_AUTO_PING', True)
MANAGEMENT_IP_ONLY = getattr(settings, 'OPENWISP_MONITORING_MANAGEMENT_IP_ONLY', True)
