from datetime import timedelta

from django.utils import timezone
from swapper import load_model

from ...device.utils import SHORT_RP
from ..settings import CONFIG_CHECK_INTERVAL
from .base import BaseCheck

AlertSettings = load_model('monitoring', 'AlertSettings')


class ConfigApplied(BaseCheck):
    def check(self, store=True):
        # If the device is down or does not have a config
        # do not run config applied check
        if self.related_object.monitoring.status in [
            'critical',
            'unknown',
        ] or not hasattr(self.related_object, 'config'):
            return
        result = int(
            self.related_object.config.status == 'applied'
            or self.related_object.modified
            > timezone.now() - timedelta(minutes=CONFIG_CHECK_INTERVAL)
        )
        # If the device config is in error status we don't need to notify
        # the user (because that's already done by openwisp-controller)
        # but we need to ensure health status will be changed
        send_alert = self.related_object.config.status != 'error'
        if store:
            self._get_metric().write(
                result, retention_policy=SHORT_RP, send_alert=send_alert
            )
        return result

    def _get_metric(self):
        metric, created = self._get_or_create_metric(configuration='config_applied')
        if created:
            self._create_alert_setting(metric)
        return metric

    def _create_alert_setting(self, metric):
        alert_s = AlertSettings(metric=metric)
        alert_s.full_clean()
        alert_s.save()
