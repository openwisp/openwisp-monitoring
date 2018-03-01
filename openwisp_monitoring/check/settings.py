from django.conf import settings

CHECK_CLASSES = getattr(settings, 'OPENWISP_MONITORING_CHECK_CLASSES', (
    ('openwisp_monitoring.check.classes.Ping', 'Ping'),
))
