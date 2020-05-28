from time import sleep

from django.apps import AppConfig
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from openwisp_notifications.types import register_notification_type
from requests.exceptions import ConnectionError

from ..db import TimeseriesDB


class MonitoringConfig(AppConfig):
    name = 'openwisp_monitoring.monitoring'
    label = 'monitoring'
    verbose_name = _('Network Monitoring')
    max_retries = 5
    retry_delay = 3

    def ready(self):
        self.create_database()
        setattr(settings, 'OPENWISP_ADMIN_SHOW_USERLINKS_BLOCK', True)
        self.register_notification_types()

    def create_database(self):
        # create influxdb database if doesn't exist yet
        for attempt_number in range(1, self.max_retries + 1):
            try:
                TimeseriesDB().create_database()
                return
            except ConnectionError as e:
                self.warn_and_delay(attempt_number)
                if attempt_number == self.max_retries:
                    raise e

    def warn_and_delay(self, attempt_number):
        print(
            'Got error while connecting to timeseries DB. '
            f'Retrying again in 3 seconds (attempt n. {attempt_number} out of 5).'
        )
        sleep(self.retry_delay)

    def register_notification_types(self):
        default_message = (
            '{notification.actor.name} for device "[{notification.target}]'
            '({notification.target_link})" {notification.verb}.'
        )

        register_notification_type(
            'threshold_crossed',
            {
                'name': 'Monitoring Alert',
                'verb': 'crossed the threshold',
                'level': 'warning',
                'email_subject': '[{site.name}] PROBLEM: {notification.actor.name} {notification.target}',
                'message': default_message,
            },
        )

        register_notification_type(
            'threshold_recovery',
            {
                'name': 'Monitoring Alert',
                'verb': 'returned within the threshold',
                'level': 'info',
                'email_subject': '[{site.name}] RECOVERY: {notification.actor.name} {notification.target}',
                'message': default_message,
            },
        )
