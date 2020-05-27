from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from openwisp_monitoring.device.base.models import (
    AbstractDeviceData,
    AbstractDeviceMonitoring,
)
from swapper import get_model_name

from openwisp_controller.config.models import Device


class DeviceData(AbstractDeviceData, Device):
    checks = GenericRelation(get_model_name('check', 'Check'))
    metrics = GenericRelation(get_model_name('monitoring', 'Metric'))

    class Meta:
        proxy = True


class DeviceMonitoring(AbstractDeviceMonitoring):
    class Meta(AbstractDeviceMonitoring.Meta):
        abstract = False


class DetailsModel(models.Model):
    details = models.CharField(max_length=64, blank=True, null=True)
