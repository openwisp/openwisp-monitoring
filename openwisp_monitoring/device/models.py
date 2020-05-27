from django.contrib.contenttypes.fields import GenericRelation
from swapper import get_model_name, swappable_setting

from openwisp_controller.config.models import Device

from .base.models import AbstractDeviceData, AbstractDeviceMonitoring


class DeviceData(AbstractDeviceData, Device):
    checks = GenericRelation(get_model_name('check', 'Check'))
    metrics = GenericRelation(get_model_name('monitoring', 'Metric'))

    class Meta:
        proxy = True
        swappable = swappable_setting('device_monitoring', 'DeviceData')


class DeviceMonitoring(AbstractDeviceMonitoring):
    class Meta(AbstractDeviceMonitoring.Meta):
        abstract = False
        swappable = swappable_setting('device_monitoring', 'DeviceMonitoring')
