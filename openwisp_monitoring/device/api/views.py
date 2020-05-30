import csv
import logging
import uuid
from collections import OrderedDict
from copy import deepcopy
from io import StringIO

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from pytz import timezone as tz
from pytz.exceptions import UnknownTimeZoneError
from rest_framework import serializers, status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from swapper import load_model

from openwisp_controller.config.models import Device

from ... import settings as monitoring_settings
from ...monitoring.exceptions import InvalidChartConfigException
from ..schema import schema
from ..settings import DEVICE_RESOURCES_THRESHOLDS
from ..signals import device_metrics_received

logger = logging.getLogger(__name__)
Graph = load_model('monitoring', 'Graph')
Metric = load_model('monitoring', 'Metric')
Threshold = load_model('monitoring', 'Threshold')
DeviceData = load_model('device_monitoring', 'DeviceData')


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
        ct = ContentType.objects.get(
            model=Device.__name__.lower(), app_label=Device._meta.app_label
        )
        graphs = Graph.objects.filter(
            metric__object_id=pk, metric__content_type=ct
        ).select_related('metric')
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
        # prepare response data
        data = self._get_graphs_data(graphs, time, timezone)
        # csv export has a different response
        if request.query_params.get('csv'):
            response = HttpResponse(self._get_csv(data), content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename=data.csv'
            return response
        return Response(data)

    def _get_graphs_data(self, graphs, time, timezone):
        graph_map = {}
        x_axys = True
        data = OrderedDict({'graphs': []})
        for graph in graphs:
            # prepare graph dict
            try:
                graph_dict = graph.read(time=time, x_axys=x_axys, timezone=timezone)
                graph_dict['description'] = graph.description
                graph_dict['title'] = graph.title.format(metric=graph.metric)
                graph_dict['type'] = graph.type
                graph_dict['unit'] = graph.unit
                graph_dict['summary_labels'] = graph.summary_labels
                graph_dict['colors'] = graph.colors
                graph_dict['colorscale'] = graph.colorscale
            except InvalidChartConfigException:
                logger.exception(f'Skipped graph for metric {graph.metric}')
                continue
            # get x axys (only once)
            if x_axys and graph_dict['x'] and graph.type != 'histogram':
                data['x'] = graph_dict.pop('x')
                x_axys = False
            # prepare to sort the items according to
            # the order in the chart configuration
            key = f'{graph.order} {graph_dict["title"]}'
            graph_map[key] = graph_dict
        # add sorted graph list to graph data
        data['graphs'] = list(OrderedDict(sorted(graph_map.items())).values())
        return data

    def _get_csv(self, data):
        header = ['time']
        columns = [data['x']]
        for graph in data['graphs']:
            # TODO: add way to export data for histogram charts
            if graph['type'] == 'histogram':
                continue
            for trace in graph['traces']:
                header.append(self._get_csv_header(graph, trace))
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

    def _get_csv_header(self, graph, trace):
        header = trace[0]
        return f'{header} - {graph["title"]}'

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
        device_metrics_received.send(
            sender=self.model, instance=self.instance, request=request
        )
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
                metric, created = Metric._get_or_create(
                    object_id=pk, content_type=ct, key=ifname, field_name=key, name=name
                )
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
            metric, created = Metric._get_or_create(
                object_id=pk,
                content_type=ct,
                key=ifname,
                field_name='clients',
                name=name,
            )
            for client in clients:
                if 'mac' not in client:
                    continue
                metric.write(client['mac'])
            if created:
                self._create_clients_graph(metric)
        if 'resources' not in data:
            return
        self._write_cpu(data['resources'], pk, ct)
        self._write_disk(data['resources'], pk, ct)
        self._write_memory(data['resources'], pk, ct)

    def _write_cpu(self, resources, primary_key, content_type):
        if 'load' not in resources:
            return
        extra_values = {
            'load_5': float(resources['load'][1]),
            'load_15': float(resources['load'][2]),
        }
        metric, created = Metric._get_or_create(
            object_id=primary_key,
            content_type=content_type,
            key='load',
            field_name='load_1',
            name='Resources: Load',
        )
        metric.write(
            float(resources['load'][0]), extra_values=extra_values,
        )
        if created:
            self._create_resources_graph(metric, resource='load')
            self._create_resources_threshold(
                metric, resource='load', cpus=resources['cpus']
            )

    def _write_disk(self, resources, primary_key, content_type):
        if 'disk' not in resources:
            return
        used_bytes, size_bytes, available_bytes = 0, 0, 0
        for disk in resources['disk']:
            used_bytes += disk['used_bytes']
            size_bytes += disk['size_bytes']
            available_bytes += disk['available_bytes']
        metric, created = Metric._get_or_create(
            object_id=primary_key,
            content_type=content_type,
            key='disk',
            field_name='used_disk',
            name='Resources: Disk',
        )
        metric.write(used_bytes / size_bytes)
        if created:
            self._create_resources_graph(metric, resource='disk')
            self._create_resources_threshold(metric, resource='disk')

    def _write_memory(self, resources, primary_key, content_type):
        if 'memory' not in resources:
            return
        memory = resources['memory']
        extra_values = {
            'total_memory': memory['total'],
            'free_memory': memory['free'],
            'buffered_memory': memory['buffered'],
            'shared_memory': memory['shared'],
            'available_memory': memory['available'],
            'cached_memory': memory['cached'],
        }
        metric, created = Metric._get_or_create(
            object_id=primary_key,
            content_type=content_type,
            key='memory',
            field_name='used_memory',
            name='Resources: Memory',
        )
        used_memory = 1 - (memory['free'] + memory['buffered']) / memory['total']
        metric.write(used_memory, extra_values=extra_values)
        if created:
            self._create_resources_graph(metric, resource='memory')
            self._create_resources_threshold(metric, resource='memory')

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
        if (
            metric.field_name != 'tx_bytes'
            or 'traffic' not in monitoring_settings.AUTO_GRAPHS
        ):
            return
        graph = Graph(metric=metric, configuration='traffic',)
        graph.full_clean()
        graph.save()

    def _create_clients_graph(self, metric):
        """
        creates "WiFi associations" graph
        """
        if 'wifi_clients' not in monitoring_settings.AUTO_GRAPHS:
            return
        graph = Graph(metric=metric, configuration='wifi_clients',)
        graph.full_clean()
        graph.save()

    def _create_resources_graph(self, metric, resource):
        if resource not in monitoring_settings.AUTO_GRAPHS:
            return
        graph = Graph(metric=metric, configuration=resource)
        graph.full_clean()
        graph.save()

    def _create_resources_threshold(self, metric, resource, cpus=None):
        value = DEVICE_RESOURCES_THRESHOLDS[resource]
        if resource == 'load':
            value = value * cpus
        t = Threshold(metric=metric, operator='>', value=value, seconds=0)
        t.full_clean()
        t.save()


device_metric = DeviceMetricView.as_view()
