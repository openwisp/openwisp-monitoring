from django.conf import settings

SHORT_RETENTION_POLICY = getattr(settings, 'OPENWISP_MONITORING_SHORT_RETENTION_POLICY', '24h0m0s')
