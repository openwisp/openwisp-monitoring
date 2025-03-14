from datetime import datetime

from django.utils import timezone
from swapper import load_model

from ...db import timeseries_db
from .. import settings as app_settings
from .base import BaseCheck

AlertSettings = load_model('monitoring', 'AlertSettings')


class WifiClients(BaseCheck):
    DATE_FORMAT = '%m-%d'
    TIME_FORMAT = '%H:%M'

    @classmethod
    def get_related_metrics(cls):
        return ('wifi_clients_min', 'wifi_clients_max')

    @classmethod
    def _get_start_end_datetime(cls, start, end, today):
        # Ensure time is included
        start = f"{start} 00:00" if ":" not in start else start
        end = f"{end} 23:59" if ":" not in end else end

        # Add date if missing
        if "-" not in start:
            start = f"{today.strftime(cls.DATE_FORMAT)} {start}"
        if "-" not in end:
            end = f"{today.strftime(cls.DATE_FORMAT)} {end}"

        # Split into date and time
        start_date, start_time = start.split()
        end_date, end_time = end.split()

        # Initialize years
        start_year, end_year = today.year, today.year

        # Adjust for time wrap-around (e.g., 23:00 to 02:00)
        if start_time > end_time:
            if today.strftime(cls.TIME_FORMAT) >= start_time:
                end_date = (today + timezone.timedelta(days=1)).strftime(
                    cls.DATE_FORMAT
                )
            else:
                start_date = (today - timezone.timedelta(days=1)).strftime(
                    cls.DATE_FORMAT
                )

        # Adjust for date wrap-around (e.g., Dec 30 to Jan 01)
        if start_date > end_date:
            if today.strftime(cls.DATE_FORMAT) >= start_date:
                end_year += 1
            else:
                start_year -= 1

        # Construct datetime objects
        start_dt = timezone.make_aware(
            datetime.strptime(
                f'{start_year}-{start_date} {start_time}', '%Y-%m-%d %H:%M'
            )
        )
        end_dt = timezone.make_aware(
            datetime.strptime(f'{end_year}-{end_date} {end_time}', '%Y-%m-%d %H:%M')
        )

        return start_dt, end_dt

    @classmethod
    def may_execute(cls):
        if app_settings.WIFI_CLIENTS_CHECK_SNOOZE_SCHEDULE:
            today = timezone.localtime()
            for (
                start_datetime,
                end_datetime,
            ) in app_settings.WIFI_CLIENTS_CHECK_SNOOZE_SCHEDULE:
                start_datetime, end_datetime = cls._get_start_end_datetime(
                    start_datetime, end_datetime, today
                )
                if start_datetime <= today <= end_datetime:
                    return False
        return True

    def _get_wifi_clients_count(self, time_interval):
        values = timeseries_db.read(
            key='wifi_clients',
            fields=['clients'],
            distinct_fields=['clients'],
            count_fields=['clients'],
            tags={
                'content_type': self.related_object._meta.label_lower,
                'object_id': str(self.related_object.pk),
            },
            since=(timezone.localtime() - timezone.timedelta(minutes=time_interval)),
        )
        if not values:
            result = 0
        else:
            result = values[0]['count']
        return result

    def _check_wifi_clients(self, check_type, interval, store=True):
        result = self._get_wifi_clients_count(interval)
        if store:
            metric = self._get_metric(f'wifi_clients_{check_type}')
            metric.write(result)
        return result

    def _check_wifi_clients_min(self, store=True):
        return self._check_wifi_clients(
            'min', app_settings.WIFI_CLIENTS_MIN_CHECK_INTERVAL, store
        )

    def _check_wifi_clients_max(self, store=True):
        return self._check_wifi_clients(
            'max', app_settings.WIFI_CLIENTS_MAX_CHECK_INTERVAL, store
        )

    def check(self, store=True):
        # If the device health status is unknown or critical,
        # then do not run the check.
        if self.related_object.monitoring.status in [
            'unknown',
            'critical',
        ]:
            return
        min = self._check_wifi_clients_min(store)
        max = self._check_wifi_clients_max(store)
        return {'wifi_clients_min': min, 'wifi_clients_max': max}

    def _get_metric(self, configuration):
        metric, created = self._get_or_create_metric(configuration=configuration)
        if created:
            self._create_alert_setting(metric)
        return metric

    def _create_alert_setting(self, metric):
        alert_s = AlertSettings(metric=metric)
        alert_s.full_clean()
        alert_s.save()
