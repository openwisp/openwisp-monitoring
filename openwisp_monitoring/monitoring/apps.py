from django.apps import AppConfig
from django.conf import settings
from django.db.models.signals import post_delete
from django.utils.translation import ugettext_lazy as _

from .utils import create_database


class MonitoringConfig(AppConfig):
    name = 'openwisp_monitoring.monitoring'
    label = 'monitoring'
    verbose_name = _('Network Monitoring')

    def ready(self):
        # create influxdb database if doesn't exist yet
        create_database()
        setattr(settings, 'OPENWISP_ADMIN_SHOW_USERLINKS_BLOCK', True)
        from ..device.models import Device
        post_delete.connect(self.delete_related_metric,
                            sender=Device,
                            dispatch_uid='delete_related_metric')

    @classmethod
    def delete_related_metric(cls, instance, **kwargs):
        from .models import Metric
        Metric.objects.filter(
            object_id=instance.pk,
            content_type__app_label=instance._meta.app_label,
            content_type__model=instance._meta.model_name
        ).delete()
