from django.utils.functional import cached_property
from netengine.backends.snmp.airos import AirOS
from netengine.backends.snmp.openwrt import OpenWRT
from swapper import load_model

from openwisp_monitoring.device.api.views import MetricChartsMixin

from .base import BaseCheck

Chart = load_model('monitoring', 'Chart')
Metric = load_model('monitoring', 'Metric')
Device = load_model('config', 'Device')
DeviceData = load_model('device_monitoring', 'DeviceData')
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
        device_data = DeviceData.objects.get(pk=pk)
        device_data.data = data
        device_data.save_data()
        self._write(pk, data)

    @cached_property
    def netengine_instance(self):
        ip = self._get_ip()
        connector = self._get_connnector()
        return connector(host=ip, **self._get_credential_params())

    @cached_property
    def credential_instance(self):
        return Credentials.objects.filter(
            deviceconnection__device_id=self.related_object, connector__endswith='Snmp',
        ).last()

    def _get_connnector(self):
        connectors = {
            'openwisp_controller.connection.connectors.snmp.Snmp': OpenWRT,
            'openwisp_controller.connection.connectors.airos.snmp.Snmp': AirOS,
        }
        try:
            return connectors.get(self.credential_instance.connector, OpenWRT)
        except AttributeError:
            # in case credentials are not available
            return OpenWRT

    def _get_credential_params(self):
        return getattr(self.credential_instance, 'params', {})
