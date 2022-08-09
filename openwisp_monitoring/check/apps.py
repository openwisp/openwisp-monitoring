from django.apps import AppConfig
from django.db.models.signals import post_save
from django.utils.translation import gettext_lazy as _
from swapper import load_model

from openwisp_monitoring.check import settings as app_settings


class CheckConfig(AppConfig):
    name = 'openwisp_monitoring.check'
    label = 'check'
    verbose_name = _('Network Monitoring Checks')

    def ready(self):
        self._connect_signals()

    def _connect_signals(self):
        if app_settings.AUTO_PING:
            from .base.models import auto_ping_receiver

            post_save.connect(
                auto_ping_receiver,
                sender=load_model('config', 'Device'),
                dispatch_uid='auto_ping',
            )

        if app_settings.AUTO_CONFIG_CHECK:
            from .base.models import auto_config_check_receiver

            post_save.connect(
                auto_config_check_receiver,
                sender=load_model('config', 'Device'),
                dispatch_uid='auto_config_check',
            )
        if app_settings.AUTO_IPERF:
            from .base.models import auto_iperf_check_receiver

            post_save.connect(
                auto_iperf_check_receiver,
                sender=load_model('config', 'Device'),
                dispatch_uid='auto_iperf_check',
            )
