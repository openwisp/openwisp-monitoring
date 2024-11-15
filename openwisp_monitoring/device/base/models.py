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
from django.db.models.signals import post_delete
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

from openwisp_controller.config.validators import mac_address_validator
from openwisp_monitoring.device.settings import get_critical_device_metrics
from openwisp_utils.base import TimeStampedEditableModel

from ...db import device_data_query, timeseries_db
from ...monitoring.signals import threshold_crossed
from ...monitoring.tasks import _timeseries_write
from ...settings import CACHE_TIMEOUT
from .. import settings as app_settings
from .. import tasks
from ..schema import schema
from ..signals import health_status_changed
from ..utils import SHORT_RP, get_device_cache_key


def mac_lookup_cache_timeout():
    """Returns a random number of hours between 48 and 96.

    This avoids timing out the entire cache at the same time.
    """
    return 60 * 60 * random.randint(48, 96)


class AbstractDeviceData(object):
    schema = schema
    __data = None
    __key = 'device_data'
    __data_timestamp = None

    def __init__(self, *args, **kwargs):
        from ..writer import DeviceDataWriter

        self.data = kwargs.pop('data', None)
        self.writer = DeviceDataWriter(self)
        super().__init__(*args, **kwargs)

    @classmethod
    @cache_memoize(CACHE_TIMEOUT)
    def get_devicedata(cls, pk):
        obj = (
            cls.objects.select_related('devicelocation')
            .only(
                'id',
                'organization_id',
                'devicelocation__location_id',
                'devicelocation__floorplan_id',
            )
            .get(id=pk)
        )
        return obj

    @classmethod
    def invalidate_cache(cls, instance, *args, **kwargs):
        if isinstance(instance, load_model('geo', 'DeviceLocation')):
            pk = instance.content_object_id
        else:
            if kwargs.get('created'):
                return
            pk = instance.pk
        cls.get_devicedata.invalidate(cls, str(pk))

    def can_be_updated(self):
        """Do not attempt to push the conf if the device is not reachable."""
        can_be_updated = super().can_be_updated()
        return can_be_updated and self.monitoring.status not in ['critical', 'unknown']

    def _get_wifi_version(self, htmode):
        wifi_version_htmode = f'{_("Other")}: {htmode}'
        if 'NOHT' in htmode:
            wifi_version_htmode = f'{_("Legacy Mode")}: {htmode}'
        elif 'HE' in htmode:
            wifi_version_htmode = f'WiFi 6 (802.11ax): {htmode}'
        elif 'VHT' in htmode:
            wifi_version_htmode = f'WiFi 5 (802.11ac): {htmode}'
        elif 'HT' in htmode:
            wifi_version_htmode = f'WiFi 4 (802.11n): {htmode}'
        return wifi_version_htmode

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
            # add wifi version
            if 'wireless' in interface and 'htmode' in interface['wireless']:
                interface['wireless']['htmode'] = self._get_wifi_version(
                    interface['wireless']['htmode']
                )

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
        """Retrieves last data snapshot from Timeseries Database."""
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
        """Sets data."""
        self.__data = data

    @property
    def data_timestamp(self):
        """Retrieves timestamp at which the data was recorded."""
        return self.__data_timestamp

    @data_timestamp.setter
    def data_timestamp(self, value):
        """Sets the timestamp related to the data."""
        self.__data_timestamp = value

    def validate_data(self):
        """Validates data according to NetJSON DeviceMonitoring schema."""
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
        """Performs corrections or additions to the device data."""
        mac_detection = app_settings.MAC_VENDOR_DETECTION
        for interface in self.data.get('interfaces', []):
            # loop over mobile signal values to convert them to float
            if 'mobile' in interface and 'signal' in interface['mobile']:
                for signal_key, signal_values in interface['mobile']['signal'].items():
                    for key, value in signal_values.items():
                        signal_values[key] = float(value)
            # If HT/VHT/HE is not being used ie. htmode = 'NOHT',
            # set the HT/VHT/HE field of WiFi clients to None.
            # This is necessary because some clients may be
            # VHT capable but VHT is not enabled at the radio level,
            # which can mislead into thinking the client is not HT/VHT/HE capable.
            wireless = interface.get('wireless')
            if wireless and all(key in wireless for key in ('htmode', 'clients')):
                for client in wireless['clients']:
                    htmode = wireless['htmode']
                    ht_enabled = htmode.startswith('HT')
                    vht_enabled = htmode.startswith('VHT')
                    noht_enabled = htmode == 'NOHT'
                    if noht_enabled:
                        client['ht'] = client['vht'] = None
                        # since 'he' field is optional
                        if 'he' in client:
                            client['he'] = None
                    elif ht_enabled:
                        if client['vht'] is False:
                            client['vht'] = None
                        if client.get('he') is False:
                            client['he'] = None
                    elif vht_enabled and client.get('he') is False:
                        client['he'] = None
            # Convert bitrate from KBits/s to MBits/s
            if wireless and 'bitrate' in wireless:
                interface['wireless']['bitrate'] = round(
                    interface['wireless']['bitrate'] / 1000.0, 1
                )
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
        """Validates and saves data to Timeseries Database."""
        self.validate_data()
        self._transform_data()
        time = time or now()
        options = dict(tags={'pk': self.pk}, timestamp=time, retention_policy=SHORT_RP)
        _timeseries_write(name=self.__key, values={'data': self.json()}, **options)
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
            timeout=CACHE_TIMEOUT,
        )
        if app_settings.WIFI_SESSIONS_ENABLED:
            self.save_wifi_clients_and_sessions()

    def json(self, *args, **kwargs):
        return json.dumps(self.data, *args, **kwargs)

    def save_wifi_clients_and_sessions(self):
        _WIFICLIENT_FIELDS = ['vendor', 'ht', 'vht', 'he', 'wmm', 'wds', 'wps']
        WifiClient = load_model('device_monitoring', 'WifiClient')
        WifiSession = load_model('device_monitoring', 'WifiSession')

        active_sessions = []
        interfaces = self.data.get('interfaces', [])
        for interface in interfaces:
            if interface.get('type') != 'wireless':
                continue
            interface_name = interface.get('name')
            wireless = interface.get('wireless', {})
            if not wireless or wireless['mode'] != 'access_point':
                continue
            ssid = wireless.get('ssid')
            clients = wireless.get('clients', [])
            for client in clients:
                # Save WifiClient
                client_obj = WifiClient.get_wifi_client(client.get('mac'))
                update_fields = []
                for field in _WIFICLIENT_FIELDS:
                    if getattr(client_obj, field) != client.get(field):
                        setattr(client_obj, field, client.get(field))
                        update_fields.append(field)
                if update_fields:
                    client_obj.full_clean()
                    client_obj.save(update_fields=update_fields)

                # Save WifiSession
                session_obj, _ = WifiSession.objects.get_or_create(
                    device_id=self.id,
                    interface_name=interface_name,
                    ssid=ssid,
                    wifi_client=client_obj,
                    stop_time=None,
                )
                active_sessions.append(session_obj.pk)

        # Close open WifiSession
        WifiSession.objects.filter(
            device_id=self.id,
            stop_time=None,
        ).exclude(
            pk__in=active_sessions
        ).update(stop_time=now())


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
        ('deactivated', _(app_settings.HEALTH_STATUS_LABELS['deactivated'])),
    )
    status = StatusField(
        _('health status'),
        db_index=True,
        help_text=_(
            '"{0}" means the device has been recently added; \n'
            '"{1}" means the device is operating normally; \n'
            '"{2}" means the device is having issues but it\'s still reachable; \n'
            '"{3}" means the device is not reachable or in critical conditions;\n'
            '"{4}" means the device is deactivated;'
        ).format(
            app_settings.HEALTH_STATUS_LABELS['unknown'],
            app_settings.HEALTH_STATUS_LABELS['ok'],
            app_settings.HEALTH_STATUS_LABELS['problem'],
            app_settings.HEALTH_STATUS_LABELS['critical'],
            app_settings.HEALTH_STATUS_LABELS['deactivated'],
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
        """Executed when a threshold is crossed.

        Changes the health status of a devicewhen a threshold defined in
        the alert settings related to the metric is crossed.
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

    @classmethod
    def handle_disabled_organization(cls, organization_id):
        """Handles the disabling of an organization.

        Clears the management IP of all devices belonging to a disabled
        organization and set their monitoring status to 'unknown'.

        Parameters: - organization_id (int): The ID of the disabled
        organization.

        Returns: - None
        """
        load_model('config', 'Device').objects.filter(
            organization_id=organization_id
        ).update(management_ip='')
        cls.objects.filter(device__organization_id=organization_id).update(
            status='unknown'
        )

    @classmethod
    def handle_deactivated_device(cls, instance, **kwargs):
        """Handles the deactivation of a device

        Sets the device's monitoring status to 'deactivated'

        Parameters: - instance (Device): The device object
        which is deactivated

        Returns: - None
        """
        cls.objects.filter(device_id=instance.id).update(status='deactivated')

    @classmethod
    def handle_activated_device(cls, instance, **kwargs):
        """Handles the activation of a deactivated device

        Sets the device's monitoring status to 'unknown'

        Parameters: - instance (Device): The device object
        which is deactivated

        Returns: - None
        """
        cls.objects.filter(device_id=instance.id).update(status='unknown')

    @classmethod
    def _get_critical_metric_keys(cls):
        return [metric['key'] for metric in get_critical_device_metrics()]

    @classmethod
    def handle_critical_metric(cls, instance, **kwargs):
        critical_metrics = cls._get_critical_metric_keys()
        if instance.check_type in critical_metrics:
            try:
                device_monitoring = cls.objects.get(device=instance.content_object)
                if not instance.is_active or kwargs.get('signal') == post_delete:
                    device_monitoring.update_status('unknown')
            except cls.DoesNotExist:
                pass


class AbstractWifiClient(TimeStampedEditableModel):
    id = None
    mac_address = models.CharField(
        max_length=17,
        db_index=True,
        primary_key=True,
        validators=[mac_address_validator],
        help_text=_('MAC address'),
    )
    vendor = models.CharField(max_length=200, blank=True, null=True)
    he = models.BooleanField(null=True, blank=True, default=None, verbose_name='HE')
    vht = models.BooleanField(null=True, blank=True, default=None, verbose_name='VHT')
    ht = models.BooleanField(null=True, blank=True, default=None, verbose_name='HT')
    wmm = models.BooleanField(default=False, verbose_name='WMM')
    wds = models.BooleanField(default=False, verbose_name='WDS')
    wps = models.BooleanField(default=False, verbose_name='WPS')

    class Meta:
        abstract = True
        verbose_name = _('WiFi Client')
        ordering = ('-created',)

    @classmethod
    @cache_memoize(CACHE_TIMEOUT)
    def get_wifi_client(cls, mac_address):
        wifi_client, _ = cls.objects.get_or_create(mac_address=mac_address)
        return wifi_client

    @classmethod
    def invalidate_cache(cls, instance, *args, **kwargs):
        if kwargs.get('created'):
            return
        cls.get_wifi_client.invalidate(cls, instance.mac_address)


class AbstractWifiSession(TimeStampedEditableModel):
    created = None

    device = models.ForeignKey(
        swapper.get_model_name('config', 'Device'),
        on_delete=models.CASCADE,
    )
    wifi_client = models.ForeignKey(
        swapper.get_model_name('device_monitoring', 'WifiClient'),
        on_delete=models.CASCADE,
    )
    ssid = models.CharField(
        max_length=32, blank=True, null=True, verbose_name=_('SSID')
    )
    interface_name = models.CharField(
        max_length=15,
    )
    start_time = models.DateTimeField(
        verbose_name=_('start time'),
        db_index=True,
        auto_now=True,
    )
    stop_time = models.DateTimeField(
        verbose_name=_('stop time'),
        db_index=True,
        null=True,
        blank=True,
    )

    class Meta:
        abstract = True
        verbose_name = _('WiFi Session')
        ordering = ('-start_time',)

    def __str__(self):
        return self.mac_address

    @property
    def mac_address(self):
        return self.wifi_client.mac_address

    @property
    def vendor(self):
        return self.wifi_client.vendor

    @classmethod
    def offline_device_close_session(
        cls, metric, tolerance_crossed, first_time, target, **kwargs
    ):
        if (
            not first_time
            and tolerance_crossed
            and not metric.is_healthy_tolerant
            and AbstractDeviceMonitoring.is_metric_critical(metric)
        ):
            tasks.offline_device_close_session.delay(device_id=target.pk)
