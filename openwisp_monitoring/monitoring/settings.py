from django.conf import settings

ADDITIONAL_CHARTS = getattr(settings, 'OPENWISP_MONITORING_CHARTS', {})
ADDITIONAL_METRICS = getattr(settings, 'OPENWISP_MONITORING_METRICS', {})

RETRY_OPTIONS = getattr(
    settings,
    'OPENWISP_MONITORING_WRITE_RETRY_OPTIONS',
    dict(
        max_retries=None, retry_backoff=True, retry_backoff_max=600, retry_jitter=True
    ),
)
