from django.contrib.contenttypes.models import ContentType
from django.utils.translation import ugettext_lazy as _
from jsonschema import validate
from jsonschema.exceptions import ValidationError as SchemaError
from rest_framework import serializers, status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from openwisp_controller.config.models import Device

from ..models import Graph, Metric
from .schema import schema


class DevicePermission(BasePermission):
    def has_object_permission(self, request, view, obj):
        return request.query_params.get('key') == obj.key


class DeviceMetricView(GenericAPIView):
    queryset = Device.objects.all()
    serializer_class = serializers.Serializer
    permission_classes = [DevicePermission]
    schema = schema
    statistics = ['rx_bytes', 'tx_bytes']

    def post(self, request, pk):
        self.instance = self.get_object()
        # validate incoming data
        try:
            self.validate(request.data)
        except SchemaError as e:
            return Response(e.message, status=status.HTTP_400_BAD_REQUEST)
        # write data
        self._write(request, self.instance.pk)
        return Response(None)

    def validate(self, data):
        """
        validate incoming data according
        to NetJSON DeviceMonitoring schema
        """
        validate(data, self.schema)

    def _write(self, request, pk):
        """
        write metrics to database
        """
        data = request.data
        ct = ContentType.objects.get(model=self.instance.__class__.__name__.lower(),
                                     app_label=self.instance._meta.app_label)
        for interface in data.get('interfaces', []):
            ifname = interface['name']
            for key, value in interface.get('statistics', {}).items():
                name = '{0} {1}'.format(ifname, key)
                metric, created = Metric.objects.get_or_create(object_id=pk,
                                                               content_type=ct,
                                                               key=ifname,
                                                               field_name=key,
                                                               name=name)
                increment = self._calculate_traffic(metric, value)
                counter = '{0}_counter'.format(key)
                # stores raw interface counter to calculate future increments
                metric.write(increment, extra_values={counter: value})
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

    def _calculate_traffic(self, metric, value):
        counter_field = '{0}_counter'.format(metric.field_name)
        # if no previous counter present, start from zero
        previous_counter = 0
        # get previous counters
        points = metric.read(limit=1, order='time DESC', extra_fields=[counter_field])
        if points:
            previous_counter = points[0][counter_field]
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
        create traffic graphs if necessary
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
        graph = Graph(metric=metric,
                      description=_('{0} daily wifi associations').format(metric.key),
                      query="SELECT COUNT(DISTINCT({field_name})) AS value FROM {key} "
                            "WHERE time >= '{time}' AND content_type = '{content_type}' "
                            "AND object_id = '{object_id}' GROUP BY time(24h) fill(0)")
        graph.full_clean()
        graph.save()


device_metric = DeviceMetricView.as_view()
