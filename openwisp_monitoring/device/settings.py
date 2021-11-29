from django.core.exceptions import ImproperlyConfigured

from ..settings import get_settings_value


def get_critical_device_metrics():
    critical_metrics = get_settings_value(
        'CRITICAL_DEVICE_METRICS',
        [{'key': 'ping', 'field_name': 'reachable'}],
    )
    for item in critical_metrics:  # pragma: no cover
        try:
            assert 'key' in item
            assert 'field_name' in item
        except AssertionError as e:
            raise ImproperlyConfigured(
                'OPENWISP_MONITORING_CRITICAL_DEVICE_METRICS must contain the following keys: key, field_name'
            ) from e
    return critical_metrics


def get_health_status_labels():
    labels = get_settings_value(
        'HEALTH_STATUS_LABELS',
        {
            'unknown': 'unknown',
            'ok': 'ok',
            'problem': 'problem',
            'critical': 'critical',
        },
    )
    try:
        assert 'unknown' in labels
        assert 'ok' in labels
        assert 'problem' in labels
        assert 'critical' in labels
    except AssertionError as e:  # pragma: no cover
        raise ImproperlyConfigured(
            'OPENWISP_MONITORING_HEALTH_STATUS_LABELS must contain the following '
            'keys: unknown, ok, problem, critical'
        ) from e
    return labels


SHORT_RETENTION_POLICY = get_settings_value('SHORT_RETENTION_POLICY', '24h0m0s')
CRITICAL_DEVICE_METRICS = get_critical_device_metrics()
HEALTH_STATUS_LABELS = get_health_status_labels()
AUTO_CLEAR_MANAGEMENT_IP = get_settings_value('AUTO_CLEAR_MANAGEMENT_IP', True)
# Triggers spontaneous recovery of device based on corresponding signals
DEVICE_RECOVERY_DETECTION = get_settings_value('DEVICE_RECOVERY_DETECTION', True)
MAC_VENDOR_DETECTION = get_settings_value('MAC_VENDOR_DETECTION', True)
DASHBOARD_MAP = get_settings_value('DASHBOARD_MAP', True)
