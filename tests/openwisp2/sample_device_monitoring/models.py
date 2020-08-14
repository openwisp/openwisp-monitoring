from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from swapper import get_model_name

from openwisp_controller.config.models import Device as BaseDevice
from openwisp_monitoring.device.base.models import (
    AbstractDeviceData,
    AbstractDeviceMonitoring,
)


class DeviceData(AbstractDeviceData, BaseDevice):
    checks = GenericRelation(get_model_name('check', 'Check'))
    metrics = GenericRelation(get_model_name('monitoring', 'Metric'))

    class Meta:
        proxy = True


class DeviceMonitoring(AbstractDeviceMonitoring):
    details = models.CharField(max_length=64, default='devicemonitoring')

    class Meta(AbstractDeviceMonitoring.Meta):
        abstract = False

    def __str__(self):
        return self.details
