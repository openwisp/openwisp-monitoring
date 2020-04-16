from django.apps import AppConfig
from django.conf import settings
from django.utils.translation import ugettext_lazy as _

from .utils import create_database


class MonitoringConfig(AppConfig):
    name = 'openwisp_monitoring.monitoring'
    label = 'monitoring'
    verbose_name = _('Network Monitoring')

    def ready(self):
        # create influxdb database if doesn't exist yet
        create_database()
        setattr(settings, 'OPENWISP_ADMIN_SHOW_USERLINKS_BLOCK', True)
