from ..settings import get_settings_value

ADDITIONAL_CHARTS = get_settings_value('CHARTS', {})
ADDITIONAL_METRICS = get_settings_value('METRICS', {})

RETRY_OPTIONS = get_settings_value(
    'WRITE_RETRY_OPTIONS',
    dict(
        max_retries=None, retry_backoff=True, retry_backoff_max=600, retry_jitter=True
    ),
)
ADDITIONAL_DASHBOARD_TRAFFIC_CHART = get_settings_value('DASHBOARD_TRAFFIC_CHART', {})
