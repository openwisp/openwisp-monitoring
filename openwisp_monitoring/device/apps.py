from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _

from .utils import manage_short_retention_policy


class DeviceMonitoringConfig(AppConfig):
    name = 'openwisp_monitoring.device'
    label = 'device_monitoring'
    verbose_name = _('Device Monitoring')

    def ready(self):
        manage_short_retention_policy()
