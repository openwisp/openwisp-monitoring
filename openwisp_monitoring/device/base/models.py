import json
import random
from collections import OrderedDict
from datetime import datetime

import swapper
from cache_memoize import cache_memoize
from dateutil.relativedelta import relativedelta
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import models
from django.dispatch import receiver
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from jsonschema import draft7_format_checker, validate
from jsonschema.exceptions import ValidationError as SchemaError
from model_utils import Choices
from model_utils.fields import StatusField
from netaddr import EUI, NotRegisteredError
from pytz import timezone as tz
from swapper import load_model

from openwisp_utils.base import TimeStampedEditableModel

from ...db import device_data_query, timeseries_db
from ...monitoring.signals import threshold_crossed
from ...monitoring.tasks import timeseries_write
from .. import settings as app_settings
from ..schema import schema
from ..signals import health_status_changed
from ..utils import SHORT_RP, get_device_cache_key


def mac_lookup_cache_timeout():
    """
    returns a random number of hours between 48 and 96
    this avoids timing out most of the cache at the same time
    """
    return 60 * 60 * random.randint(48, 96)


class AbstractDeviceData(object):
    schema = schema
    __data = None
    __key = 'device_data'
    __data_timestamp = None

    def __init__(self, *args, **kwargs):
        self.data = kwargs.pop('data', None)
        super().__init__(*args, **kwargs)

    def can_be_updated(self):
        """
        Do not attempt at pushing the conf if the device is not reachable
        """
        can_be_updated = super().can_be_updated()
        return can_be_updated and self.monitoring.status not in ['critical', 'unknown']

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
        # reformat expiry in dhcp leases
        for lease in data.get('dhcp_leases', []):
            lease['expiry'] = datetime.fromtimestamp(lease['expiry'], tz=tz('UTC'))
        return data

    @property
    def data(self):
        """
        retrieves last data snapshot from Timeseries Database
        """
        if self.__data:
            return self.__data
        q = device_data_query.format(SHORT_RP, self.__key, self.pk)
        cache_key = get_device_cache_key(device=self, context='current-data')
        points = cache.get(cache_key)
        if not points:
            points = timeseries_db.get_list_query(q, precision=None)
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

    def _transform_data(self):
        """
        performs corrections or additions to the device data
        """
        mac_detection = app_settings.MAC_VENDOR_DETECTION
        for interface in self.data.get('interfaces', []):
            # loop over mobile signal values to convert them to float
            if 'mobile' in interface and 'signal' in interface['mobile']:
                for signal_key, signal_values in interface['mobile']['signal'].items():
                    for key, value in signal_values.items():
                        signal_values[key] = float(value)
            # add mac vendor to wireless clients if present
            if (
                not mac_detection
                or 'wireless' not in interface
                or 'clients' not in interface['wireless']
            ):
                continue
            for client in interface['wireless']['clients']:
                client['vendor'] = self._mac_lookup(client['mac'])
        if not mac_detection:
            return
        # add mac vendor to neighbors
        for neighbor in self.data.get('neighbors', []):
            # in some cases the mac_address may not be present
            # eg: neighbors with "FAILED" state
            neighbor['vendor'] = self._mac_lookup(neighbor.get('mac'))
        # add mac vendor to DHCP leases
        for lease in self.data.get('dhcp_leases', []):
            lease['vendor'] = self._mac_lookup(lease['mac'])

    @cache_memoize(mac_lookup_cache_timeout())
    def _mac_lookup(self, value):
        if not value:
            return ''
        try:
            return EUI(value).oui.registration().org
        except NotRegisteredError:
            return ''

    def save_data(self, time=None):
        """
        validates and saves data to Timeseries Database
        """
        self.validate_data()
        self._transform_data()
        time = time or now()
        options = dict(tags={'pk': self.pk}, timestamp=time, retention_policy=SHORT_RP)
        timeseries_write.delay(name=self.__key, values={'data': self.json()}, **options)
        cache_key = get_device_cache_key(device=self, context='current-data')
        # cache current data to allow getting it without querying the timeseries DB
        cache.set(
            cache_key,
            [
                {
                    'data': self.json(),
                    'time': time.astimezone(tz=tz('UTC')).isoformat(timespec='seconds'),
                }
            ],
            timeout=86400,  # 24 hours
        )

    def json(self, *args, **kwargs):
        return json.dumps(self.data, *args, **kwargs)


class AbstractDeviceMonitoring(TimeStampedEditableModel):
    device = models.OneToOneField(
        swapper.get_model_name('config', 'Device'),
        on_delete=models.CASCADE,
        related_name='monitoring',
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
        # clear device management_ip when device is offline
        if self.status == 'critical' and app_settings.AUTO_CLEAR_MANAGEMENT_IP:
            self.device.management_ip = None
            self.device.save(update_fields=['management_ip'])

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
    @receiver(threshold_crossed, dispatch_uid='threshold_crossed_receiver')
    def threshold_crossed(sender, metric, alert_settings, target, first_time, **kwargs):
        """
        Changes the health status of a devicewhen a threshold defined in the
        alert settings related to the metric is crossed.
        """
        DeviceMonitoring = load_model('device_monitoring', 'DeviceMonitoring')
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
