from django.conf import settings

AUTO_CHARTS = getattr(
    settings,
    'OPENWISP_MONITORING_AUTO_CHARTS',
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
