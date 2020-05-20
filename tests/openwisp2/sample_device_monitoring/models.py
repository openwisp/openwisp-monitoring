from django.db import models
from openwisp_monitoring.device.models import DeviceData as BaseDeviceData
from openwisp_monitoring.device.models import DeviceMonitoring as BaseDeviceMonitoring


class DeviceData(BaseDeviceData):
    class Meta:
        proxy = True


class DetailsModel(models.Model):
    details = models.CharField(max_length=64, blank=True, null=True)


class DeviceMonitoring(BaseDeviceMonitoring):
    class Meta(BaseDeviceMonitoring.Meta):
        proxy = True
