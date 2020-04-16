from django.apps import AppConfig
from django.db.models.signals import post_delete
from django.utils.translation import ugettext_lazy as _

from .utils import manage_short_retention_policy


class DeviceMonitoringConfig(AppConfig):
    name = 'openwisp_monitoring.device'
    label = 'device_monitoring'
    verbose_name = _('Device Monitoring')

    def ready(self):
        manage_short_retention_policy()
        self.connect_device_post_delete()

    def connect_device_post_delete(self):
        from openwisp_controller.config.models import Device

        post_delete.connect(
            self.device_post_delete_receiver,
            sender=Device,
            dispatch_uid='device_post_delete_receiver',
        )

    @classmethod
    def device_post_delete_receiver(cls, instance, **kwargs):
        from ..device.models import DeviceData

        instance.__class__ = DeviceData
        instance.checks.all().delete()
        instance.metrics.all().delete()
