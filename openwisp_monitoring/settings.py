from django.conf import settings

AUTO_GRAPHS = getattr(settings, 'OPENWISP_MONITORING_AUTO_GRAPHS', (
    'traffic', 'wifi_clients', 'uptime', 'packet_loss', 'rtt',
))
