from django.conf import settings

ADDITIONAL_CHART_OPERATIONS = getattr(
    settings, 'OPENWISP_MONITORING_ADDITIONAL_CHART_OPERATIONS', {}
)
