from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

SHORT_RETENTION_POLICY = getattr(settings, 'OPENWISP_MONITORING_SHORT_RETENTION_POLICY', '24h0m0s')
CRITICAL_DEVICE_METRICS = getattr(settings, 'OPENWISP_MONITORING_CRITICAL_DEVICE_METRICS', [
    {'key': 'ping', 'field_name': 'reachable'}
])

for item in CRITICAL_DEVICE_METRICS:
    if not all(['key' in item, 'field_name' in item]):
        raise ImproperlyConfigured(
            'OPENWISP_MONITORING_CRITICAL_DEVICE_METRICS contains invalid items'
        )
