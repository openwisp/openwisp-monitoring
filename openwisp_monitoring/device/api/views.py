from copy import deepcopy

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers, status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from ...monitoring.models import Graph, Metric
from ..models import DeviceData
from ..schema import schema


class DevicePermission(BasePermission):
    def has_object_permission(self, request, view, obj):
        return request.query_params.get('key') == obj.key


class DeviceMetricView(GenericAPIView):
    queryset = DeviceData.objects.all()
    serializer_class = serializers.Serializer
    permission_classes = [DevicePermission]
    schema = schema
    statistics_stored = ['rx_bytes', 'tx_bytes']

    def post(self, request, pk):
        self.instance = self.get_object()
        self._init_previous_data()
        self.instance.data = request.data
        # validate incoming data
        try:
            self.instance.validate_data()
        except ValidationError as e:
            return Response(e.message, status=status.HTTP_400_BAD_REQUEST)
        # write data
        self._write(request, self.instance.pk)
        return Response(None)

    def _init_previous_data(self):
        """
        makes NetJSON interfaces of previous
        snapshots more easy to access
        """
        data = self.instance.data or {}
        if data:
            data = deepcopy(data)
            data['interfaces_dict'] = {}
        for interface in data.get('interfaces', []):
            data['interfaces_dict'][interface['name']] = interface
        self._previous_data = data

    def _write(self, request, pk):
        """
        write metrics to database
        """
        # saves raw device data
        self.instance.save_data()
        data = self.instance.data
        ct = ContentType.objects.get(model='device', app_label='config')
        for interface in data.get('interfaces', []):
            ifname = interface['name']
            for key, value in interface.get('statistics', {}).items():
                if key not in self.statistics_stored:
                    continue
                name = '{0} {1}'.format(ifname, key)
                metric, created = Metric.objects.get_or_create(object_id=pk,
                                                               content_type=ct,
                                                               key=ifname,
                                                               field_name=key,
                                                               name=name)
                increment = self._calculate_increment(ifname, key, value)
                metric.write(increment)
                if created:
                    self._create_traffic_graph(metric)
            if 'clients' not in interface:
                continue
            name = '{0} wifi clients'.format(ifname)
            metric, created = Metric.objects.get_or_create(object_id=pk,
                                                           content_type=ct,
                                                           key=ifname,
                                                           field_name='clients',
                                                           name=name)
            for client in interface.get('clients', {}).keys():
                metric.write(client)
            if created:
                self._create_clients_graph(metric)

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

    def _create_traffic_graph(self, metric):
        """
        create "daily traffic (GB)" graph
        """
        if metric.field_name != 'tx_bytes':
            return
        graph = Graph(metric=metric,
                      description=_('{0} daily traffic (GB)').format(metric.key),
                      query="SELECT SUM(tx_bytes) / 1000000000 AS download, "
                            "SUM(rx_bytes) / 1000000000 AS upload FROM {key} "
                            "WHERE time >= '{time}' AND content_type = '{content_type}' "
                            "AND object_id = '{object_id}' GROUP BY time(24h) fill(0)")
        graph.full_clean()
        graph.save()

    def _create_clients_graph(self, metric):
        """
        creates "daily wifi associations" graph
        """
        graph = Graph(metric=metric,
                      description=_('{0} daily wifi associations').format(metric.key),
                      query="SELECT COUNT(DISTINCT({field_name})) AS value FROM {key} "
                            "WHERE time >= '{time}' AND content_type = '{content_type}' "
                            "AND object_id = '{object_id}' GROUP BY time(24h) fill(0)")
        graph.full_clean()
        graph.save()


device_metric = DeviceMetricView.as_view()
