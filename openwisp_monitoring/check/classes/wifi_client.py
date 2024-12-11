from django.utils import timezone
from swapper import load_model

from ...db import timeseries_db
from .. import settings as app_settings
from .base import BaseCheck

AlertSettings = load_model('monitoring', 'AlertSettings')


class WifiClient(BaseCheck):
    def check(self, store=True):
        values = timeseries_db.read(
            key='wifi_clients',
            fields='COUNT(DISTINCT(clients))',
            tags={
                'content_type': self.related_object._meta.label_lower,
                'object_id': str(self.related_object.pk),
            },
            since=int(
                (
                    timezone.localtime()
                    - timezone.timedelta(
                        minutes=app_settings.WIFI_CLIENT_CHECK_INTERVAL
                    )
                ).timestamp()
            ),
        )
        if not values:
            result = 0
        else:
            result = values[0]['count']
        if store:
            self.store_result(result)
        return result

    def store_result(self, result):
        max_metric = self._get_metric('max_wifi_clients')
        max_metric.write(result)
        min_metric = self._get_metric('min_wifi_clients')
        min_metric.write(result)

    def _get_metric(self, configuration):
        metric, created = self._get_or_create_metric(configuration=configuration)
        if created:
            self._create_alert_setting(metric)
        return metric

    def _create_alert_setting(self, metric):
        alert_s = AlertSettings(metric=metric)
        alert_s.full_clean()
        alert_s.save()
