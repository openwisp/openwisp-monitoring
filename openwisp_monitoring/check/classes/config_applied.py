from swapper import load_model

from ...device.utils import SHORT_RP
from .base import BaseCheck

AlertSettings = load_model('monitoring', 'AlertSettings')


class ConfigApplied(BaseCheck):
    def check(self, store=True):
        # If the device is down do not run config applied checks
        if self.related_object.monitoring.status in ['critical', 'unknown']:
            return
        if not hasattr(self.related_object, 'config'):
            return
        result = int(self.related_object.config.status == 'applied')
        if store:
            self._get_metric().write(
                result, retention_policy=SHORT_RP,
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
