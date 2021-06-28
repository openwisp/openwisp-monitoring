from django.conf import settings


def get_settings_value(option, default=None):
    return getattr(settings, f'OPENWISP_MONITORING_{option}', default)


AUTO_CHARTS = get_settings_value(
    'AUTO_CHARTS',
    (
        'traffic',
        'wifi_clients',
        'uptime',
        'packet_loss',
        'rtt',
        'memory',
        'cpu',
        'disk',
    ),
)
