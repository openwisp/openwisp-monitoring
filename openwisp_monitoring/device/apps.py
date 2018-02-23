from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class DeviceMonitoringConfig(AppConfig):
    name = 'openwisp_monitoring.device'
    label = 'device_monitoring'
    verbose_name = _('Device Monitoring')
