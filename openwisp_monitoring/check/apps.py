from django.apps import AppConfig
from django.db.models.signals import post_save
from django.utils.translation import gettext_lazy as _
from swapper import load_model

from openwisp_monitoring.check import checks  # noqa


class CheckConfig(AppConfig):
    name = 'openwisp_monitoring.check'
    label = 'check'
    verbose_name = _('Network Monitoring Checks')

    def ready(self):
        self._connect_signals()

    def _connect_signals(self):
        Check = load_model('check', 'Check')

        post_save.connect(
            Check.auto_create_check_receiver,
            sender=load_model('config', 'Device'),
            dispatch_uid='auto_create_check',
        )
