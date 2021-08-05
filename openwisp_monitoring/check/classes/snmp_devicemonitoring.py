from django.utils.functional import cached_property
from netengine.backends.snmp.openwrt import OpenWRT
from swapper import load_model

from openwisp_monitoring.device.api.views import MetricChartsMixin

from .base import BaseCheck

Chart = load_model('monitoring', 'Chart')
Metric = load_model('monitoring', 'Metric')
Device = load_model('config', 'Device')
Credentials = load_model('connection', 'Credentials')
AlertSettings = load_model('monitoring', 'AlertSettings')


class SnmpDeviceMonitoring(BaseCheck, MetricChartsMixin):
    def check(self, store=True):
        result = self.netengine_instance.to_dict()
        self._init_previous_data(data=getattr(self.related_object, 'data', {}))
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
        ip = self._get_ip()
        return OpenWRT(host=ip, **self._get_credential_params())

    def _get_credential_params(self):
        cred = Credentials.objects.filter(
            deviceconnection__device_id=self.related_object,
            connector='openwisp_controller.connection.connectors.snmp.Snmp',
        ).last()
        return getattr(cred, 'params', {})
