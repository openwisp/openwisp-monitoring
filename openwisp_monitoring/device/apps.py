from django.apps import AppConfig
from django.conf import settings
from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.utils.translation import gettext_lazy as _
from swapper import load_model

from openwisp_controller.config.signals import checksum_requested, config_modified
from openwisp_controller.connection import settings as connection_settings
from openwisp_controller.connection.signals import is_working_changed

from ..check import settings as check_settings
from ..utils import transaction_on_commit
from . import settings as app_settings
from .signals import device_metrics_received, health_status_changed
from .utils import get_device_cache_key, manage_short_retention_policy


class DeviceMonitoringConfig(AppConfig):
    name = 'openwisp_monitoring.device'
    label = 'device_monitoring'
    verbose_name = _('Device Monitoring')

    def ready(self):
        manage_short_retention_policy()
        self.connect_is_working_changed()
        self.connect_device_signals()
        self.connect_config_modified()
        self.device_recovery_detection()
        self.set_update_config_model()

    def connect_device_signals(self):
        Device = load_model('config', 'Device')

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
        if not app_settings.DEVICE_RECOVERY_DETECTION:
            return

        Device = load_model('config', 'Device')
        DeviceData = load_model('device_monitoring', 'DeviceData')
        DeviceMonitoring = load_model('device_monitoring', 'DeviceMonitoring')
        health_status_changed.connect(
            self.manage_device_recovery_cache_key,
            sender=DeviceMonitoring,
            dispatch_uid='recovery_health_status_changed',
        )
        checksum_requested.connect(
            self.trigger_device_recovery_checks,
            sender=Device,
            dispatch_uid='recovery_checksum_requested',
        )
        device_metrics_received.connect(
            self.trigger_device_recovery_checks,
            sender=DeviceData,
            dispatch_uid='recovery_device_metrics_received',
        )

    @classmethod
    def manage_device_recovery_cache_key(cls, instance, status, **kwargs):
        """
        It sets the ``cache_key`` as 1 when device ``health_status`` goes to ``critical``
        and deletes the ``cache_key`` when device recovers from ``critical`` state
        """
        cache_key = get_device_cache_key(device=instance.device)
        if status == 'critical':
            cache.set(cache_key, 1, timeout=None)
        else:
            cache.delete(cache_key)

    @classmethod
    def trigger_device_recovery_checks(cls, instance, **kwargs):
        from .tasks import trigger_device_checks

        if cache.get(get_device_cache_key(device=instance)):
            transaction_on_commit(lambda: trigger_device_checks.delay(pk=instance.pk))

    @classmethod
    def connect_is_working_changed(cls):
        is_working_changed.connect(
            cls.is_working_changed_receiver,
            sender=load_model('connection', 'DeviceConnection'),
            dispatch_uid='is_working_changed_monitoring',
        )

    @classmethod
    def is_working_changed_receiver(
        cls, instance, is_working, old_is_working, failure_reason, **kwargs
    ):
        from .tasks import trigger_device_checks

        Check = load_model('check', 'Check')
        device = instance.device
        device_monitoring = device.monitoring
        # if old_is_working is None, it's a new device connection which wasn't
        # ever used yet, so nothing is really changing and we don't need to do anything
        if old_is_working is None and is_working:
            return
        # if device is down because of connectivity issues, it's probably due
        # to reboot caused by firmware upgrade, avoid notifications
        ignored_failures = ['Unable to connect', 'timed out']
        for message in ignored_failures:
            if message in failure_reason:
                device_monitoring.save()
                return
        initial_status = device_monitoring.status
        status = 'ok' if is_working else 'problem'
        # do not send notifications if recovery made after firmware upgrade
        if status == initial_status == 'ok':
            device_monitoring.save()
            return
        if not is_working:
            if initial_status == 'ok':
                transaction_on_commit(lambda: trigger_device_checks.delay(pk=device.pk))
        else:
            # if checks exist trigger them else, set status as 'ok'
            if Check.objects.filter(object_id=instance.device.pk).exists():
                transaction_on_commit(lambda: trigger_device_checks.delay(pk=device.pk))
            else:
                device_monitoring.update_status(status)

    @classmethod
    def connect_config_modified(cls):
        Config = load_model('config', 'Config')

        if check_settings.AUTO_CONFIG_CHECK:
            config_modified.connect(
                cls.config_modified_receiver,
                sender=Config,
                dispatch_uid='config_modified',
            )

    @classmethod
    def config_modified_receiver(cls, sender, instance, **kwargs):
        from ..check.tasks import perform_check

        DeviceData = load_model('device_monitoring', 'DeviceData')
        device = DeviceData.objects.get(config=instance)
        check = device.checks.filter(check__contains='ConfigApplied').first()
        if check:
            transaction_on_commit(lambda: perform_check.delay(check.pk))

    def set_update_config_model(self):
        if not getattr(settings, 'OPENWISP_UPDATE_CONFIG_MODEL', None):
            setattr(
                connection_settings,
                'UPDATE_CONFIG_MODEL',
                'device_monitoring.DeviceData',
            )
