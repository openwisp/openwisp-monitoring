from django.apps import AppConfig
from django.db.models.signals import post_delete
from django.utils.translation import ugettext_lazy as _


class CheckConfig(AppConfig):
    name = 'openwisp_monitoring.check'
    label = 'check'
    verbose_name = _('Network Monitoring Checks')

    def ready(self):
        from ..device.models import Device
        post_delete.connect(self.delete_related_check,
                            sender=Device,
                            dispatch_uid='delete_related_check')

    @classmethod
    def delete_related_check(cls, instance, **kwargs):
        from .models import Check
        Check.objects.filter(
            object_id=instance.pk,
            content_type__app_label=instance._meta.app_label,
            content_type__model=instance._meta.model_name
        ).delete()
