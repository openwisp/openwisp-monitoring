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
