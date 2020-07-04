from django.conf import settings

ADDITIONAL_CHARTS = getattr(settings, 'OPENWISP_MONITORING_CHARTS', {})
ADDITIONAL_METRICS = getattr(settings, 'OPENWISP_MONITORING_METRICS', {})
