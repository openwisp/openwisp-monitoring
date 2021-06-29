from copy import deepcopy

from django.contrib.contenttypes.models import ContentType
from django.utils.functional import cached_property
from netengine.backends.snmp.openwrt import OpenWRT
from swapper import load_model

from ... import settings as monitoring_settings
from .. import settings as app_settings
from .base import BaseCheck

Chart = load_model('monitoring', 'Chart')
Metric = load_model('monitoring', 'Metric')
Device = load_model('config', 'Device')
AlertSettings = load_model('monitoring', 'AlertSettings')


class SnmpDeviceMonitoring(BaseCheck):
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
        ct = ContentType.objects.get_for_model(Device)
        pk = self.related_object.pk
        for interface in data.get('interfaces', []):
            ifname = interface['name']
            ifstats = interface.get('statistics', {})
            # Explicitly stated None to avoid skipping in case the stats are zero
            if (
                ifstats.get('rx_bytes') is not None
                and ifstats.get('rx_bytes') is not None
            ):
                field_value = self._calculate_increment(
                    ifname, 'rx_bytes', ifstats['rx_bytes']
                )
                extra_values = {
                    'tx_bytes': self._calculate_increment(
                        ifname, 'tx_bytes', ifstats['tx_bytes']
                    )
                }
                name = f'{ifname} traffic'
                metric, created = Metric._get_or_create(
                    object_id=pk,
                    content_type=ct,
                    configuration='traffic',
                    name=name,
                    key=ifname,
                )
                metric.write(field_value, extra_values=extra_values)
                if created:
                    self._create_traffic_chart(metric)
            try:
                clients = interface['wireless']['clients']
            except KeyError:
                continue
            if not isinstance(clients, list):
                continue
            name = '{0} wifi clients'.format(ifname)
            metric, created = Metric._get_or_create(
                object_id=pk,
                content_type=ct,
                configuration='clients',
                name=name,
                key=ifname,
            )
            for client in clients:
                if 'mac' not in client:
                    continue
                metric.write(client['mac'])
            if created:
                self._create_clients_chart(metric)
        if 'resources' not in data:
            return
        if 'load' in data['resources'] and 'cpus' in data['resources']:
            self._write_cpu(
                data['resources']['load'], data['resources']['cpus'], pk, ct
            )
        if 'disk' in data['resources']:
            self._write_disk(data['resources']['disk'], pk, ct)
        if 'memory' in data['resources']:
            self._write_memory(data['resources']['memory'], pk, ct)

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

    def _write_cpu(self, load, cpus, primary_key, content_type):
        extra_values = {
            'load_1': float(load[0]),
            'load_5': float(load[1]),
            'load_15': float(load[2]),
        }
        metric, created = Metric._get_or_create(
            object_id=primary_key, content_type=content_type, configuration='cpu'
        )
        if created:
            self._create_resources_chart(metric, resource='cpu')
            self._create_resources_alert_settings(metric, resource='cpu')
        metric.write(100 * float(load[0] / cpus), extra_values=extra_values)

    def _write_disk(self, disk_list, primary_key, content_type):
        used_bytes, size_bytes, available_bytes = 0, 0, 0
        for disk in disk_list:
            used_bytes += disk['used_bytes']
            size_bytes += disk['size_bytes']
            available_bytes += disk['available_bytes']
        metric, created = Metric._get_or_create(
            object_id=primary_key, content_type=content_type, configuration='disk'
        )
        if created:
            self._create_resources_chart(metric, resource='disk')
            self._create_resources_alert_settings(metric, resource='disk')
        metric.write(100 * used_bytes / size_bytes)

    def _write_memory(self, memory, primary_key, content_type):
        extra_values = {
            'total_memory': memory['total'],
            'free_memory': memory['free'],
            'buffered_memory': memory['shared'],
            'shared_memory': memory['shared'],
        }
        if 'cached' in memory:
            extra_values['cached_memory'] = memory.get('cached')
        percent_used = 100 * (1 - (memory['free'] + memory['shared']) / memory['total'])
        # Available Memory is not shown in some systems (older openwrt versions)
        if 'available' in memory:
            extra_values.update({'available_memory': memory['available']})
            if memory['available'] > memory['free']:
                percent_used = 100 * (
                    1 - (memory['available'] + memory['shared']) / memory['total']
                )
        metric, created = Metric._get_or_create(
            object_id=primary_key, content_type=content_type, configuration='memory'
        )
        if created:
            self._create_resources_chart(metric, resource='memory')
            self._create_resources_alert_settings(metric, resource='memory')
        metric.write(percent_used, extra_values=extra_values)

    def _calculate_increment(self, ifname, stat, value):
        """
        compares value with previously stored counter and
        calculates the increment of the value (which is returned)
        """
        # get previous counters
        data = self._previous_data
        try:
            previous_counter = data['interfaces_dict'][ifname]['statistics'][stat]
        except KeyError:
            # if no previous measurements present, counter will start from zero
            previous_counter = 0
        # if current value is higher than previous value,
        # it means the interface traffic counter is increasing
        # and to calculate the traffic performed since the last
        # measurement we have to calculate the difference
        if value >= previous_counter:
            return value - previous_counter
        # on the other side, if the current value is less than
        # the previous value, it means that the counter was restarted
        # (eg: reboot, configuration reload), so we keep the whole amount
        else:
            return value

    def _create_traffic_chart(self, metric):
        """
        create "traffic (GB)" chart
        """
        if 'traffic' not in monitoring_settings.AUTO_CHARTS:
            return
        chart = Chart(metric=metric, configuration='traffic')
        chart.full_clean()
        chart.save()

    def _create_clients_chart(self, metric):
        """
        creates "WiFi associations" chart
        """
        if 'wifi_clients' not in monitoring_settings.AUTO_CHARTS:
            return
        chart = Chart(metric=metric, configuration='wifi_clients')
        chart.full_clean()
        chart.save()

    def _create_resources_chart(self, metric, resource):
        if resource not in monitoring_settings.AUTO_CHARTS:
            return
        chart = Chart(metric=metric, configuration=resource)
        chart.full_clean()
        chart.save()

    def _create_resources_alert_settings(self, metric, resource):
        alert_settings = AlertSettings(metric=metric)
        alert_settings.full_clean()
        alert_settings.save()

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
