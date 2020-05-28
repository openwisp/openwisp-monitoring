from django.conf import settings

ADDITIONAL_CHARTS = getattr(settings, 'OPENWISP_MONITORING_CHARTS', {})
