from django.db import models
from django.utils.translation import ugettext_lazy as _
from model_utils import Choices
from model_utils.fields import StatusField
from swapper import load_model

from openwisp_utils.base import TimeStampedEditableModel

from .. import settings as app_settings
from ..signals import health_status_changed


class AbstractDeviceMonitoring(TimeStampedEditableModel):
    device = models.OneToOneField(
        'config.Device', on_delete=models.CASCADE, related_name='monitoring'
    )
    STATUS = Choices(
        ('unknown', _(app_settings.HEALTH_STATUS_LABELS['unknown'])),
        ('ok', _(app_settings.HEALTH_STATUS_LABELS['ok'])),
        ('problem', _(app_settings.HEALTH_STATUS_LABELS['problem'])),
        ('critical', _(app_settings.HEALTH_STATUS_LABELS['critical'])),
    )
    status = StatusField(
        _('health status'),
        db_index=True,
        help_text=_(
            '"{0}" means the device has been recently added; \n'
            '"{1}" means the device is operating normally; \n'
            '"{2}" means the device is having issues but it\'s still reachable; \n'
            '"{3}" means the device is not reachable or in critical conditions;'
        ).format(
            app_settings.HEALTH_STATUS_LABELS['unknown'],
            app_settings.HEALTH_STATUS_LABELS['ok'],
            app_settings.HEALTH_STATUS_LABELS['problem'],
            app_settings.HEALTH_STATUS_LABELS['critical'],
        ),
    )

    class Meta:
        abstract = True

    def update_status(self, value):
        # don't trigger save nor emit signal if status is not changing
        if self.status == value:
            return
        self.status = value
        self.full_clean()
        self.save()
        health_status_changed.send(sender=self.__class__, instance=self, status=value)

    @property
    def related_metrics(self):
        Metric = load_model('monitoring', 'Metric')
        return Metric.objects.select_related('content_type').filter(
            object_id=self.device_id,
            content_type__model='device',
            content_type__app_label='config',
        )

    @staticmethod
    def is_metric_critical(metric):
        for critical in app_settings.CRITICAL_DEVICE_METRICS:
            if all(
                [
                    metric.key == critical['key'],
                    metric.field_name == critical['field_name'],
                ]
            ):
                return True
        return False
