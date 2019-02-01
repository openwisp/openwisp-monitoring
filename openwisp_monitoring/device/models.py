import json

from django.core.exceptions import ValidationError
from django.db import models
from django.dispatch import receiver
from django.utils.translation import ugettext_lazy as _
from jsonschema import validate
from jsonschema.exceptions import ValidationError as SchemaError
from model_utils import Choices
from model_utils.fields import StatusField

from openwisp_controller.config.models import Device
from openwisp_utils.base import TimeStampedEditableModel

from ..monitoring.models import Metric
from ..monitoring.signals import threshold_crossed
from ..monitoring.utils import query, write
from .schema import schema
from .signals import health_status_changed
from .utils import SHORT_RP
from . import settings as app_settings


class DeviceData(Device):
    schema = schema
    __data = None
    __key = 'device_data'

    class Meta:
        proxy = True

    def __init__(self, *args, **kwargs):
        self.data = kwargs.pop('data', None)
        return super(DeviceData, self).__init__(*args, **kwargs)

    @property
    def data(self):
        """
        retrieves last data snapshot from influxdb
        """
        if self.__data:
            return self.__data
        q = "SELECT data FROM {0}.{1} WHERE pk = '{2}' " \
            "ORDER BY time DESC LIMIT 1".format(SHORT_RP, self.__key, self.pk)
        points = list(query(q).get_points())
        if not points:
            return None
        return json.loads(points[0]['data'])

    @data.setter
    def data(self, data):
        """
        sets data
        """
        self.__data = data

    def validate_data(self):
        """
        validate data according to NetJSON DeviceMonitoring schema
        """
        try:
            validate(self.data, self.schema)
        except SchemaError as e:
            path = [str(el) for el in e.path]
            trigger = '/'.join(path)
            message = 'Invalid data in "#/{0}", '\
                      'validator says:\n\n{1}'.format(trigger, e.message)
            raise ValidationError(message)

    def save_data(self, time=None):
        """
        validates and saves data to influxdb
        """
        self.validate_data()
        write(name=self.__key,
              values={'data': self.json()},
              tags={'pk': self.pk},
              timestamp=time,
              retention_policy=SHORT_RP)

    def json(self, *args, **kwargs):
        return json.dumps(self.data, *args, **kwargs)


class DeviceMonitoring(TimeStampedEditableModel):
    device = models.OneToOneField('config.Device', on_delete=models.CASCADE,
                                  related_name='monitoring')
    STATUS = Choices('ok', 'problem', 'critical')
    status = StatusField(_('health status'), db_index=True, help_text=_(
        '"ok" means the device is operating normally; \n'
        '"problem" problem means the device is having issues but it\'s still reachable; \n'
        '"critical" means the device is not reachable or in critical conditions;'
    ))

    def update_status(self, value):
        # don't trigger save nor emit signal if status is not changing
        if self.status == value:
            return
        self.status = value
        self.full_clean()
        self.save()
        health_status_changed.send(sender=self.__class__,
                                   instance=self,
                                   status=value)

    @property
    def related_metrics(self):
        return Metric.objects.select_related('content_type')\
                             .filter(object_id=self.device_id,
                                     content_type__model='device',
                                     content_type__app_label='config')

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
        elif not metric.is_healthy and any([monitoring.is_metric_critical(metric),
                                            related_status == 'critical']):
            status = 'critical'
        monitoring.update_status(status)

    @staticmethod
    def is_metric_critical(metric):
        for critical in app_settings.CRITICAL_DEVICE_METRICS:
            if all([metric.key == critical['key'],
                    metric.field_name == critical['field_name']]):
                return True
        return False
