import json
from collections import OrderedDict
from datetime import datetime

from dateutil.relativedelta import relativedelta
from django.contrib.contenttypes.fields import GenericRelation
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save
from django.dispatch import receiver
from jsonschema import draft7_format_checker, validate
from jsonschema.exceptions import ValidationError as SchemaError
from mac_vendor_lookup import MacLookup
from pytz import timezone as tz
from swapper import is_swapped, swappable_setting

from openwisp_controller.config.models import Device

from ..monitoring.signals import threshold_crossed
from ..monitoring.utils import query, write
from . import settings as app_settings
from .base.models import AbstractDeviceMonitoring
from .schema import schema
from .utils import SHORT_RP

mac_lookup = MacLookup()


class DeviceData(Device):
    schema = schema
    __data = None
    __key = 'device_data'
    __data_timestamp = None

    if is_swapped('check', 'Check'):
        checks = GenericRelation(is_swapped('check', 'Check'))
    else:
        checks = GenericRelation('check.Check')
    if is_swapped('monitoring', 'Metric'):
        metrics = GenericRelation(is_swapped('monitoring', 'Metric'))
    else:
        metrics = GenericRelation('monitoring.Metric')

    class Meta:
        proxy = True

    def __init__(self, *args, **kwargs):
        self.data = kwargs.pop('data', None)
        return super().__init__(*args, **kwargs)

    @property
    def data_user_friendly(self):
        if not self.data:
            return None
        data = self.data
        # slicing to eliminate the nanoseconds from timestamp
        measured_at = datetime.strptime(self.data_timestamp[0:19], '%Y-%m-%dT%H:%M:%S')
        time_elapsed = int((datetime.utcnow() - measured_at).total_seconds())
        if 'general' in data and 'local_time' in data['general']:
            local_time = data['general']['local_time']
            data['general']['local_time'] = datetime.fromtimestamp(
                local_time + time_elapsed, tz=tz('UTC')
            )
        if 'general' in data and 'uptime' in data['general']:
            uptime = '{0.days} days, {0.hours} hours and {0.minutes} minutes'
            data['general']['uptime'] = uptime.format(
                relativedelta(seconds=data['general']['uptime'] + time_elapsed)
            )
        if 'resources' in data and 'memory' in data['resources']:
            # convert bytes to megabytes
            MB = 1000000.0
            for key in data['resources']['memory'].keys():
                data['resources']['memory'][key] = round(
                    data['resources']['memory'][key] / MB, 2
                )
        # used for reordering interfaces
        interface_dict = OrderedDict()
        for interface in data.get('interfaces', []):
            # don't show interfaces if they don't have any useful info
            if len(interface.keys()) <= 2:
                continue
            # human readable wireless  mode
            if 'wireless' in interface and 'mode' in interface['wireless']:
                interface['wireless']['mode'] = interface['wireless']['mode'].replace(
                    '_', ' '
                )
            # convert to GHz
            if 'wireless' in interface and 'frequency' in interface['wireless']:
                interface['wireless']['frequency'] /= 1000
            interface_dict[interface['name']] = interface
        # reorder interfaces in alphabetical order
        interface_dict = OrderedDict(sorted(interface_dict.items()))
        data['interfaces'] = list(interface_dict.values())
        return data

    @property
    def data(self):
        """
        retrieves last data snapshot from influxdb
        """
        if self.__data:
            return self.__data
        q = (
            "SELECT data FROM {0}.{1} WHERE pk = '{2}' "
            "ORDER BY time DESC LIMIT 1".format(SHORT_RP, self.__key, self.pk)
        )
        points = list(query(q).get_points())
        if not points:
            return None
        self.data_timestamp = points[0]['time']
        return json.loads(points[0]['data'])

    @data.setter
    def data(self, data):
        """
        sets data
        """
        self.__data = data

    @property
    def data_timestamp(self):
        """
        retrieves timestamp at which the data was recorded
        """
        return self.__data_timestamp

    @data_timestamp.setter
    def data_timestamp(self, value):
        """
        sets the timestamp related to the data
        """
        self.__data_timestamp = value

    def validate_data(self):
        """
        validate data according to NetJSON DeviceMonitoring schema
        """
        try:
            validate(self.data, self.schema, format_checker=draft7_format_checker)
        except SchemaError as e:
            path = [str(el) for el in e.path]
            trigger = '/'.join(path)
            message = 'Invalid data in "#/{0}", ' 'validator says:\n\n{1}'.format(
                trigger, e.message
            )
            raise ValidationError(message)

    def add_mac_vendor_info(self):
        for interface in self.data.get('interfaces', []):
            if 'wireless' not in interface or 'clients' not in interface['wireless']:
                continue
            for client in interface['wireless']['clients']:
                client['vendor'] = self._mac_lookup(client['mac'])
        for neighbor in self.data.get('neighbors', []):
            neighbor['vendor'] = self._mac_lookup(neighbor['mac_address'])

    def _mac_lookup(self, value):
        try:
            return mac_lookup.lookup(value)
        except KeyError:
            return ''

    def save_data(self, time=None):
        """
        validates and saves data to influxdb
        """
        self.validate_data()
        if app_settings.MAC_VENDOR_DETECTION:
            self.add_mac_vendor_info()
        write(
            name=self.__key,
            values={'data': self.json()},
            tags={'pk': self.pk},
            timestamp=time,
            retention_policy=SHORT_RP,
        )

    def json(self, *args, **kwargs):
        return json.dumps(self.data, *args, **kwargs)


class DeviceMonitoring(AbstractDeviceMonitoring):
    class Meta(AbstractDeviceMonitoring.Meta):
        abstract = False
        swappable = swappable_setting('device_monitoring', 'DeviceMonitoring')

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
