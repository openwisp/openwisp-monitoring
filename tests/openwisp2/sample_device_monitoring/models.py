from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from openwisp_monitoring.device.base.models import AbstractDeviceMonitoring
from openwisp_monitoring.device.models import DeviceData
from openwisp_monitoring.monitoring.signals import threshold_crossed

from openwisp_controller.config.models import Device

DeviceData = DeviceData


class DetailsModel(models.Model):
    details = models.CharField(max_length=64, blank=True, null=True)


class DeviceMonitoring(AbstractDeviceMonitoring):
    class Meta(AbstractDeviceMonitoring.Meta):
        abstract = False

    @staticmethod
    @receiver(threshold_crossed, dispatch_uid='threshold_crossed_receiver')
    def threshold_crossed(sender, metric, threshold, target, **kwargs):
        """
        Changes the health status of a device when a threshold is crossed.
        """
        if not isinstance(target, DeviceMonitoring.device.field.related_model):
            return
        try:
            monitoring = target.monitoring
        except DeviceMonitoring.DoesNotExist:
            monitoring = DeviceMonitoring.objects.create(device=target)
        status = 'ok' if metric.is_healthy else 'problem'
        related_status = 'ok'
        for related_metric in monitoring.related_metrics.filter(is_healthy=False):
            if monitoring.is_metric_critical(related_metric):
                related_status = 'critical'
                break
            related_status = 'problem'
        if metric.is_healthy and related_status == 'problem':
            status = 'problem'
        elif metric.is_healthy and related_status == 'critical':
            status = 'critical'
        elif not metric.is_healthy and any(
            [monitoring.is_metric_critical(metric), related_status == 'critical']
        ):
            status = 'critical'
        monitoring.update_status(status)


@receiver(post_save, sender=Device, dispatch_uid='create_device_monitoring')
def device_monitoring_receiver(sender, instance, created, **kwargs):
    if created:
        DeviceMonitoring.objects.create(device=instance)
