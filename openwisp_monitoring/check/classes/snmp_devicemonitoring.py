from copy import deepcopy

from django.contrib.contenttypes.models import ContentType
from django.utils.functional import cached_property
from netengine.backends.snmp.openwrt import OpenWRT
from swapper import load_model

from openwisp_monitoring.device.api.views import MetricChartsMixin

from ... import settings as monitoring_settings
from .. import settings as app_settings
from .base import BaseCheck

Chart = load_model('monitoring', 'Chart')
Metric = load_model('monitoring', 'Metric')
Device = load_model('config', 'Device')
AlertSettings = load_model('monitoring', 'AlertSettings')


class SnmpDeviceMonitoring(BaseCheck, MetricChartsMixin):
    def check(self, store=True):
        result = self.netengine_instance.to_dict()
        self._init_previous_data()
        self.related_object.data = result
        if store:
            self.store_result(result)
        return result

    def store_result(self, data):
        """
        store result in the DB
        """
        pk = self.related_object.pk
        self._write(pk, data)

    @cached_property
    def netengine_instance(self):
        params = self.params['credential_params']
        ip = self._get_ip()
        return OpenWRT(host=ip, **params)

    def _get_ip(self):
        """
        Figures out ip to use or fails raising OperationalError
        """
        device = self.related_object
        ip = device.management_ip
        if not ip and not app_settings.MANAGEMENT_IP_ONLY:
            ip = device.last_ip
        return ip

    def _init_previous_data(self):
        """
        makes NetJSON interfaces of previous
        snapshots more easy to access
        """
        data = getattr(self.related_object, 'data', {})
        if data:
            data = deepcopy(data)
            data['interfaces_dict'] = {}
        for interface in data.get('interfaces', []):
            data['interfaces_dict'][interface['name']] = interface
        self._previous_data = data
