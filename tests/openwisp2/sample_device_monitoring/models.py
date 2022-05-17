from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from swapper import get_model_name, load_model

from openwisp_monitoring.device.base.models import (
    AbstractDeviceData,
    AbstractDeviceMonitoring,
    AbstractWifiClient,
    AbstractWifiSession,
)

BaseDevice = load_model('config', 'Device', require_ready=False)


class DetailsModel(models.Model):
    details = models.CharField(max_length=64, default='devicemonitoring')

    class Meta:
        abstract = True


class DeviceData(AbstractDeviceData, BaseDevice):
    checks = GenericRelation(get_model_name('check', 'Check'))
    metrics = GenericRelation(get_model_name('monitoring', 'Metric'))

    class Meta:
        proxy = True


class DeviceMonitoring(DetailsModel, AbstractDeviceMonitoring):
    class Meta(AbstractDeviceMonitoring.Meta):
        abstract = False

    def __str__(self):
        return self.details


class WifiClient(DetailsModel, AbstractWifiClient):
    class Meta(AbstractWifiClient.Meta):
        abstract = False


class WifiSession(DetailsModel, AbstractWifiSession):
    class Meta(AbstractWifiSession.Meta):
        abstract = False
