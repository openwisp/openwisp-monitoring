from django.utils import timezone
from swapper import load_model

from ...db import timeseries_db
from ...device.utils import SHORT_RP
from .. import settings as app_settings
from .base import BaseCheck

AlertSettings = load_model('monitoring', 'AlertSettings')
Metric = load_model('monitoring', 'Metric')


class DataCollected(BaseCheck):
    @classmethod
    def get_related_metrics(cls):
        return ('data_collected',)

    def check(self, store=True):
        device_monitoring = self.related_object.monitoring
        active_metrics = device_monitoring.get_active_metrics()
        passive_metrics = device_monitoring.related_metrics.exclude(
            configuration__in=active_metrics
        ).values_list('key', flat=True)
        if passive_metrics:
            # Perform a query to the timeseries database to get the last
            # written point for every passive metric. This is done to optimize
            # the query instead of iterating over each metric and getting
            # its last written point individually.
            points = timeseries_db.read(
                key=','.join(set(passive_metrics)),
                fields='*',
                tags={
                    'content_type': self.related_object._meta.label_lower,
                    'object_id': str(self.related_object.pk),
                },
                since=(
                    timezone.localtime()
                    - timezone.timedelta(
                        minutes=app_settings.DATA_COLLECTED_CHECK_INTERVAL
                    )
                ),
                limit=1,
                order_by='-time',
            )
            result = int(len(points) > 0)
        else:
            result = 0
        send_alert = device_monitoring.status != 'critical'
        if store:
            self.timed_store(result, send_alert)
        return {'data_collected': result}

    def store(self, result, send_alert, *args, **kwargs):
        self._get_metric().write(
            result, retention_policy=SHORT_RP, send_alert=send_alert
        )

    def _get_metric(self):
        metric, created = self._get_or_create_metric(configuration='data_collected')
        if created:
            self._create_alert_setting(metric)
        return metric

    def _create_alert_setting(self, metric):
        alert_s = AlertSettings(metric=metric)
        alert_s.full_clean()
        alert_s.save()
