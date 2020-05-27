from django.apps import AppConfig
from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.utils.translation import ugettext_lazy as _
from django_netjsonconfig.signals import checksum_requested
from openwisp_notifications.signals import notify
from swapper import load_model

from . import settings as app_settings
from .signals import device_metrics_received, health_status_changed
from .utils import get_device_recovery_cache_key, manage_short_retention_policy


class DeviceMonitoringConfig(AppConfig):
    name = 'openwisp_monitoring.device'
    label = 'device_monitoring'
    verbose_name = _('Device Monitoring')

    def ready(self):
        manage_short_retention_policy()
        self.connect_is_working_changed()
        self.connect_device_signals()
        self.device_recovery_detection()

    def connect_device_signals(self):
        from openwisp_controller.config.models import Device

        post_save.connect(
            self.device_post_save_receiver,
            sender=Device,
            dispatch_uid='device_post_save_receiver',
        )

        post_delete.connect(
            self.device_post_delete_receiver,
            sender=Device,
            dispatch_uid='device_post_delete_receiver',
        )

    @classmethod
    def device_post_save_receiver(cls, instance, created, **kwargs):
        if created:
            DeviceMonitoring = load_model('device_monitoring', 'DeviceMonitoring')
            DeviceMonitoring.objects.create(device=instance)

    @classmethod
    def device_post_delete_receiver(cls, instance, **kwargs):
        DeviceData = load_model('device_monitoring', 'DeviceData')
        instance.__class__ = DeviceData
        instance.checks.all().delete()
        instance.metrics.all().delete()

    def device_recovery_detection(self):
        if app_settings.DEVICE_RECOVERY_DETECTION:
            from openwisp_controller.config.models import Device

            DeviceData = load_model('device_monitoring', 'DeviceData')
            DeviceMonitoring = load_model('device_monitoring', 'DeviceMonitoring')
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
        from .tasks import trigger_device_checks

        if cache.get(get_device_recovery_cache_key(device=instance)):
            trigger_device_checks.delay(pk=instance.pk)

    @classmethod
    def connect_is_working_changed(self):
        from openwisp_controller.connection.models import DeviceConnection
        from openwisp_controller.connection.signals import is_working_changed

        is_working_changed.connect(
            self.is_working_changed_receiver,
            sender=DeviceConnection,
            dispatch_uid='is_working_changed_monitoring',
        )

    @classmethod
    def is_working_changed_receiver(cls, instance, is_working, **kwargs):
        from .tasks import trigger_device_checks

        Check = load_model('check', 'Check')
        device = instance.device
        device_monitoring = device.monitoring
        initial_status = device_monitoring.status
        status = 'ok' if is_working else 'problem'
        if not is_working:
            # Create a related notification explaining why it's not working
            desc = instance.failure_reason
            opts = dict(
                sender=device, level='warning', verb='not working', description=desc
            )
            if initial_status == 'ok':
                trigger_device_checks.delay(pk=device.pk)
        else:
            # create a notification that device is working
            desc = f'{device} has connected successfully.'
            opts = dict(
                sender=device,
                level='info',
                verb='connected successfully',
                description=desc,
            )
            # if checks exist trigger them else, set status as 'ok'
            if Check.objects.filter(object_id=instance.device.pk).exists():
                trigger_device_checks.delay(pk=device.pk)
            else:
                device_monitoring.update_status(status)
        opts['data'] = {'email_subject': f'[{status.upper()}] {device}'}
        notify.send(**opts)
