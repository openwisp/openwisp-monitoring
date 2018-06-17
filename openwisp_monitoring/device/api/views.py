import csv
import uuid
from collections import OrderedDict
from copy import deepcopy
from io import StringIO

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.utils.translation import ugettext_lazy as _
from pytz import timezone as tz
from pytz.exceptions import UnknownTimeZoneError
from rest_framework import serializers, status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from ... import settings as monitoring_settings
from ...monitoring.models import Graph, Metric
from ..models import DeviceData
from ..schema import schema


class DevicePermission(BasePermission):
    def has_object_permission(self, request, view, obj):
        return request.query_params.get('key') == obj.key


class DeviceMetricView(GenericAPIView):
    model = DeviceData
    queryset = DeviceData.objects.all()
    serializer_class = serializers.Serializer
    permission_classes = [DevicePermission]
    schema = schema
    statistics_stored = ['rx_bytes', 'tx_bytes']

    def get(self, request, pk):
        # ensure valid UUID
        try:
            pk = str(uuid.UUID(pk))
        except ValueError:
            return Response({'detail': 'not found'}, status=404)
        self.instance = self.get_object()
        device_model = self.model.mro()[1]
        ct = ContentType.objects.get(model=device_model.__name__.lower(),
                                     app_label=device_model._meta.app_label)
        graphs = Graph.objects.filter(metric__object_id=pk,
                                      metric__content_type=ct) \
                              .order_by('-description')
        # determine time range
        time = request.query_params.get('time', Graph.DEFAULT_TIME)
        if time not in Graph.GROUP_MAP.keys():
            return Response({'detail': 'Time range not supported'}, status=400)
        # try to read timezone
        timezone = request.query_params.get('timezone', settings.TIME_ZONE)
        try:
            tz(timezone)
        except UnknownTimeZoneError:
            return Response('Unkown Time Zone', status=400)
        # get graphs and their data
        data = OrderedDict({'graphs': []})
        x_axys = True
        for graph in graphs:
            g = graph.read(time=time, x_axys=x_axys, timezone=timezone)
            # avoid repeating the x axys each time
            if x_axys and g['x']:
                data['x'] = g.pop('x')
                x_axys = False
            g['description'] = graph.description
            data['graphs'].append(g)
        if request.query_params.get('csv'):
            response = HttpResponse(self._get_csv(data), content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename=data.csv'
            return response
        return Response(data)

    def _get_csv(self, data):
        header = ['time']
        columns = [data['x']]
        for graph in data['graphs']:
            for trace in graph['traces']:
                header.append(trace[0])
                columns.append(trace[1])
        rows = [header]
        for index, element in enumerate(data['x']):
            row = []
            for column in columns:
                row.append(column[index])
            rows.append(row)
        # write CSV to in-memory file object
        fileobj = StringIO()
        csv.writer(fileobj).writerows(rows)
        return fileobj.getvalue()

    def post(self, request, pk):
        self.instance = self.get_object()
        self._init_previous_data()
        self.instance.data = request.data
        # validate incoming data
        try:
            self.instance.validate_data()
        except ValidationError as e:
            return Response(e.message, status=status.HTTP_400_BAD_REQUEST)
        try:
            # write data
            self._write(request, self.instance.pk)
        except ValidationError as e:
            return Response(e.message_dict, status=status.HTTP_400_BAD_REQUEST)
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
                metric, created = Metric._get_or_create(object_id=pk,
                                                        content_type=ct,
                                                        key=ifname,
                                                        field_name=key,
                                                        name=name)
                increment = self._calculate_increment(ifname, key, value)
                metric.write(increment)
                if created:
                    self._create_traffic_graph(metric)
            try:
                clients = interface['wireless']['clients']
            except KeyError:
                continue
            if not isinstance(clients, list):
                continue
            name = '{0} wifi clients'.format(ifname)
            metric, created = Metric._get_or_create(object_id=pk,
                                                    content_type=ct,
                                                    key=ifname,
                                                    field_name='clients',
                                                    name=name)
            for client in clients:
                if 'mac' not in client:
                    continue
                metric.write(client['mac'])
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
        create "traffic (GB)" graph
        """
        if (metric.field_name != 'tx_bytes' or 'traffic' not in monitoring_settings.AUTO_GRAPHS):
            return
        graph = Graph(metric=metric,
                      description=_('{0} traffic (GB)').format(metric.key),
                      query="SELECT SUM(tx_bytes) / 1000000000 AS upload, "
                            "SUM(rx_bytes) / 1000000000 AS download FROM {key} "
                            "WHERE time >= '{time}' AND content_type = '{content_type}' "
                            "AND object_id = '{object_id}' GROUP BY time(24h) fill(0)")
        graph.full_clean()
        graph.save()

    def _create_clients_graph(self, metric):
        """
        creates "WiFi associations" graph
        """
        if 'wifi_clients' not in monitoring_settings.AUTO_GRAPHS:
            return
        graph = Graph(metric=metric,
                      description=_('{0} clients').format(metric.key),
                      query="SELECT COUNT(DISTINCT({field_name})) AS value FROM {key} "
                            "WHERE time >= '{time}' AND content_type = '{content_type}' "
                            "AND object_id = '{object_id}' GROUP BY time(24h) fill(0)")
        graph.full_clean()
        graph.save()


device_metric = DeviceMetricView.as_view()
