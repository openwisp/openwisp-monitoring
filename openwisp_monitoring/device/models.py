from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from swapper import get_model_name, load_model, swappable_setting

from .base.models import (
    AbstractDeviceData,
    AbstractDeviceMonitoring,
    AbstractWifiClient,
    AbstractWifiSession,
)

BaseDevice = load_model('config', 'Device', require_ready=False)


class DeviceData(AbstractDeviceData, BaseDevice):
    checks = GenericRelation(get_model_name('check', 'Check'))
    metrics = GenericRelation(get_model_name('monitoring', 'Metric'))

    class Meta:
        proxy = True
        swappable = swappable_setting('device_monitoring', 'DeviceData')

    def handle_unknown_status_change(self, instance, **kwargs):
        critical_metrics = settings.OPENWISP_MONITORING_CRITICAL_DEVICE_METRICS
        if instance.metric.name in critical_metrics:
            if kwargs.get('created', False):
                self.update_status('unknown')
            elif kwargs.get('sender', None).__name__ == 'Check':
                self.update_status('unknown')

    def handle_critical_check_change(cls, check):
        critical_metrics = settings.OPENWISP_MONITORING_CRITICAL_DEVICE_METRICS
        device_data_instances = DeviceData.objects.filter(pk=check.object_id)
        for instance in device_data_instances:
            if check.metric.name in critical_metrics:
                instance.update_status('unknown')


class DeviceMonitoring(AbstractDeviceMonitoring):
    class Meta(AbstractDeviceMonitoring.Meta):
        abstract = False
        swappable = swappable_setting('device_monitoring', 'DeviceMonitoring')


class WifiClient(AbstractWifiClient):
    class Meta(AbstractWifiClient.Meta):
        abstract = False
        swappable = swappable_setting('device_monitoring', 'WifiClient')


class WifiSession(AbstractWifiSession):
    class Meta(AbstractWifiSession.Meta):
        abstract = False
        swappable = swappable_setting('device_monitoring', 'WifiSession')
