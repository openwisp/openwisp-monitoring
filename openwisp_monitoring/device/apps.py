from django.apps import AppConfig
from django.core.cache import cache
from django.db.models.signals import post_delete
from django.utils.translation import ugettext_lazy as _
from django_netjsonconfig.signals import checksum_requested

from . import settings as app_settings
from .signals import device_metrics_received, health_status_changed
from .utils import get_device_recovery_cache_key, manage_short_retention_policy


class DeviceMonitoringConfig(AppConfig):
    name = 'openwisp_monitoring.device'
    label = 'device_monitoring'
    verbose_name = _('Device Monitoring')

    def ready(self):
        manage_short_retention_policy()
        self.connect_device_post_delete()
        self.device_recovery_detection()

    def connect_device_post_delete(self):
        from openwisp_controller.config.models import Device

        post_delete.connect(
            self.device_post_delete_receiver,
            sender=Device,
            dispatch_uid='device_post_delete_receiver',
        )

    def device_recovery_detection(self):
        if app_settings.DEVICE_RECOVERY_DETECTION:
            from openwisp_controller.config.models import Device
            from .models import DeviceData, DeviceMonitoring

            health_status_changed.connect(
                self.manage_device_recovery_cache_key, sender=DeviceMonitoring
            )
            checksum_requested.connect(
                self.trigger_device_recovery_checks,
                sender=Device,
                dispatch_uid='checksum_requested',
            )
            device_metrics_received.connect(
                self.trigger_device_recovery_checks,
                sender=DeviceData,
                dispatch_uid='received_device_metrics',
            )

    @classmethod
    def device_post_delete_receiver(cls, instance, **kwargs):
        from ..device.models import DeviceData

        instance.__class__ = DeviceData
        instance.checks.all().delete()
        instance.metrics.all().delete()

    @classmethod
    def manage_device_recovery_cache_key(cls, instance, status, **kwargs):
        """
        It sets the ``cache_key`` as 1 when device ``health_status`` goes to ``critical``
        and deletes the ``cache_key`` when device recovers from ``critical`` state
        """
        cache_key = get_device_recovery_cache_key(device=instance.device)
        if status == 'critical':
            cache.set(cache_key, 1, timeout=None)
        else:
            cache.delete(cache_key)

    @classmethod
    def trigger_device_recovery_checks(cls, instance, **kwargs):
        from .tasks import trigger_device_recovery

        if cache.get(get_device_recovery_cache_key(device=instance)):
            trigger_device_recovery.delay(pk=instance.pk)
