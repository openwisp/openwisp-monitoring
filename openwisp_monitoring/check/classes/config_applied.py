from datetime import datetime

from django.conf import settings
from pytz import timezone
from swapper import load_model

from ...device.utils import SHORT_RP
from ..settings import CONFIG_CHECK_INTERVAL
from .base import BaseCheck

AlertSettings = load_model('monitoring', 'AlertSettings')


class ConfigApplied(BaseCheck):
    def _get_result(self, config_status, config_modified_mins_ago):
        """
        Returns zero, if the config is not applied and the config was modified
        more than OPENWISP_MONITORING_CONFIG_CHECK_INTERVAL mins ago, otherwise returns one
        """
        return int(
            not (
                config_status != 'applied'
                and config_modified_mins_ago > CONFIG_CHECK_INTERVAL
            )
        )

    def check(self, store=True):
        # If the device is down or does not have a config
        # do not run config applied check
        if self.related_object.monitoring.status in [
            'critical',
            'unknown',
        ] or not hasattr(self.related_object, 'config'):
            return
        config_status = self.related_object.config.status
        config_modified_datetime = self.related_object.config.modified.astimezone(
            timezone(settings.TIME_ZONE)
        )
        time_now_diff = (
            datetime.now(tz=timezone(settings.TIME_ZONE)) - config_modified_datetime
        )
        config_modified_mins_ago = round(time_now_diff.total_seconds() / 60)
        result = self._get_result(config_status, config_modified_mins_ago)
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
