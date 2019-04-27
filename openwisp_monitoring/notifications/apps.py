from django.utils.translation import ugettext_lazy as _
from notifications.apps import Config


class NotificationsConfig(Config):
    name = 'openwisp_monitoring.notifications'
    label = 'notifications'
    verbose_name = _('Notifications')
