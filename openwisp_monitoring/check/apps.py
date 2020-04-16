from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class CheckConfig(AppConfig):
    name = 'openwisp_monitoring.check'
    label = 'check'
    verbose_name = _('Network Monitoring Checks')
