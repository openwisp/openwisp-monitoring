import csv
import logging
import uuid
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timedelta
from io import StringIO

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db.models import Count, Q
from django.http import HttpResponse
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from pytz import UTC
from pytz import timezone as tz
from pytz.exceptions import UnknownTimeZoneError
from rest_framework import serializers, status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from swapper import load_model

from openwisp_controller.geo.api.views import (
    DevicePermission,
    GeoJsonLocationList,
    LocationDeviceList,
)

from ... import settings as monitoring_settings
from ...monitoring.configuration import ACCESS_TECHNOLOGIES
from ...monitoring.exceptions import InvalidChartConfigException
from ..schema import schema
from ..signals import device_metrics_received
from .serializers import MonitoringDeviceSerializer, MonitoringGeoJsonLocationSerializer

logger = logging.getLogger(__name__)
Chart = load_model('monitoring', 'Chart')
Metric = load_model('monitoring', 'Metric')
AlertSettings = load_model('monitoring', 'AlertSettings')
Device = load_model('config', 'Device')
DeviceMonitoring = load_model('device_monitoring', 'DeviceMonitoring')
DeviceData = load_model('device_monitoring', 'DeviceData')
Location = load_model('geo', 'Location')


class DeviceMetricView(GenericAPIView):
    model = DeviceData
    queryset = DeviceData.objects.select_related('devicelocation').all()
    serializer_class = serializers.Serializer
    permission_classes = [DevicePermission]
    schema = schema

    def get(self, request, pk):
        # ensure valid UUID
        try:
            pk = str(uuid.UUID(pk))
        except ValueError:
            return Response({'detail': 'not found'}, status=404)
        self.instance = self.get_object()
        ct = ContentType.objects.get_for_model(Device)
        charts = Chart.objects.filter(
            metric__object_id=pk, metric__content_type=ct
        ).select_related('metric')
        # determine time range
        time = request.query_params.get('time', Chart.DEFAULT_TIME)
        if time not in Chart.GROUP_MAP.keys():
            return Response({'detail': 'Time range not supported'}, status=400)
        # try to read timezone
        timezone = request.query_params.get('timezone', settings.TIME_ZONE)
        try:
            tz(timezone)
        except UnknownTimeZoneError:
            return Response('Unkown Time Zone', status=400)
        # prepare response data
        data = self._get_charts_data(charts, time, timezone)
        # csv export has a different response
        if request.query_params.get('csv'):
            response = HttpResponse(self._get_csv(data), content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename=data.csv'
            return response
        # add device data if requested
        if request.query_params.get('status', False):
            data['data'] = self.instance.data
        return Response(data)

    def _get_charts_data(self, charts, time, timezone):
        chart_map = {}
        x_axys = True
        data = OrderedDict({'charts': []})
        for chart in charts:
            # prepare chart dict
            try:
                chart_dict = chart.read(time=time, x_axys=x_axys, timezone=timezone)
                if not chart_dict['traces']:
                    continue
                chart_dict['description'] = chart.description
                chart_dict['title'] = chart.title.format(
                    metric=chart.metric, **chart.metric.tags
                )
                chart_dict['type'] = chart.type
                chart_dict['unit'] = chart.unit
                chart_dict['summary_labels'] = chart.summary_labels
                chart_dict['colors'] = chart.colors
                chart_dict['colorscale'] = chart.colorscale
                for attr in ['fill', 'xaxis', 'yaxis']:
                    value = getattr(chart, attr)
                    if value:
                        chart_dict[attr] = value
            except InvalidChartConfigException:
                logger.exception(f'Skipped chart for metric {chart.metric}')
                continue
            # get x axys (only once)
            if x_axys and chart_dict['x'] and chart.type != 'histogram':
                data['x'] = chart_dict.pop('x')
                x_axys = False
            # prepare to sort the items according to
            # the order in the chart configuration
            key = f'{chart.order} {chart_dict["title"]}'
            chart_map[key] = chart_dict
        # add sorted chart list to chart data
        data['charts'] = list(OrderedDict(sorted(chart_map.items())).values())
        return data

    def _get_csv(self, data):
        header = ['time']
        columns = [data.get('x')]
        histograms = []
        for chart in data['charts']:
            if chart['type'] == 'histogram':
                histograms.append(chart)
                continue
            for trace in chart['traces']:
                header.append(self._get_csv_header(chart, trace))
                columns.append(trace[1])
        rows = [header]
        for index, element in enumerate(data.get('x', [])):
            row = []
            for column in columns:
                row.append(column[index])
            rows.append(row)
        for chart in histograms:
            rows.append([])
            rows.append([chart['title']])
            # Export value as 0 if it is None
            for key, value in chart['summary'].items():
                if chart['summary'][key] is None:
                    chart['summary'][key] = 0
            # Sort Histogram on the basis of value in the descending order
            sorted_charts = sorted(
                chart['summary'].items(), key=lambda x: x[1], reverse=True
            )
            for field, value in sorted_charts:
                rows.append([field, value])
        # write CSV to in-memory file object
        fileobj = StringIO()
        csv.writer(fileobj).writerows(rows)
        return fileobj.getvalue()

    def _get_csv_header(self, chart, trace):
        header = trace[0]
        return f'{header} - {chart["title"]}'

    def post(self, request, pk):
        self.instance = self.get_object()
        self._init_previous_data()
        self.instance.data = request.data
        # validate incoming data
        try:
            self.instance.validate_data()
        except ValidationError as e:
            logger.info(e.message)
            return Response(e.message, status=status.HTTP_400_BAD_REQUEST)
        time_obj = request.query_params.get(
            'time', now().utcnow().strftime('%d-%m-%Y_%H:%M:%S.%f')
        )
        current = request.query_params.get('current', False)
        try:
            time = datetime.strptime(time_obj, '%d-%m-%Y_%H:%M:%S.%f').replace(
                tzinfo=UTC
            )
        except ValueError:
            return Response({'detail': _('Incorrect time format')}, status=400)
        try:
            # write data
            self._write(request, self.instance.pk, time=time)
        except ValidationError as e:
            logger.info(e.message_dict)
            return Response(e.message_dict, status=status.HTTP_400_BAD_REQUEST)
        device_metrics_received.send(
            sender=self.model,
            instance=self.instance,
            request=request,
            time=time,
            current=current,
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

    def _write(self, request, pk, time=None, current=False):
        """
        write metrics to database
        """
        # saves raw device data
        self.instance.save_data()
        data = self.instance.data
        ct = ContentType.objects.get_for_model(Device)
        device_extra_tags = self._get_extra_tags(self.instance)
        for interface in data.get('interfaces', []):
            ifname = interface['name']
            extra_tags = Metric._sort_dict(device_extra_tags)
            if 'mobile' in interface:
                self._write_mobile_signal(interface, ifname, ct, pk, current, time=time)
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
                    key='traffic',
                    main_tags={'ifname': Metric._makekey(ifname)},
                    extra_tags=extra_tags,
                )
                metric.write(field_value, current, time=time, extra_values=extra_values)
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
                key='wifi_clients',
                main_tags={'ifname': Metric._makekey(ifname)},
                extra_tags=extra_tags,
            )
            # avoid tsdb overwrite clients
            client_time = time
            for client in clients:
                if 'mac' not in client:
                    continue
                metric.write(client['mac'], current, time=client_time)
                client_time += timedelta(microseconds=1)
            if created:
                self._create_clients_chart(metric)
        if 'resources' not in data:
            return
        if 'load' in data['resources'] and 'cpus' in data['resources']:
            self._write_cpu(
                data['resources']['load'],
                data['resources']['cpus'],
                pk,
                ct,
                current,
                time=time,
            )
        if 'disk' in data['resources']:
            self._write_disk(data['resources']['disk'], pk, ct, time=time)
        if 'memory' in data['resources']:
            self._write_memory(data['resources']['memory'], pk, ct, current, time=time)

    def _get_extra_tags(self, device):
        tags = {'organization_id': str(device.organization_id)}
        try:
            device_location = device.devicelocation
        except ObjectDoesNotExist:
            pass
        else:
            tags['location_id'] = str(device_location.location_id)
            if device_location.floorplan_id:
                tags['floorplan_id'] = str(device_location.floorplan_id)
        return tags

    def _get_mobile_signal_type(self, signal):
        if not signal:
            return
        # if only one access technology in use, return that
        sections = list(signal.keys())
        if len(sections) == 1:
            return sections[0]
        # if multiple access technologies are in use,
        # return the most advanced one
        access_technologies = list(ACCESS_TECHNOLOGIES.keys())
        access_technologies.reverse()
        for tech in access_technologies:
            if tech in signal:
                return tech

    def _write_mobile_signal(self, interface, ifname, ct, pk, current=False, time=None):
        access_type = self._get_mobile_signal_type(interface['mobile'].get('signal'))
        if not access_type:
            return
        data = interface['mobile']['signal'][access_type]
        signal_power = signal_strength = None
        extra_values = {}
        if 'rssi' in data:
            signal_strength = data['rssi']
        if 'rsrp' in data:
            signal_power = data['rsrp']
        elif 'rscp' in data:
            signal_power = data['rscp']
        if signal_power is not None:
            extra_values = {'signal_power': float(signal_power)}
        if signal_strength is not None:
            signal_strength = float(signal_strength)
        if signal_strength is not None or signal_power is not None:
            metric, created = Metric._get_or_create(
                object_id=pk,
                content_type=ct,
                configuration='signal_strength',
                name='signal strength',
                key=ifname,
            )
            metric.write(signal_strength, current, time=time, extra_values=extra_values)
            if created:
                self._create_signal_strength_chart(metric)

        snr = signal_quality = None
        extra_values = {}
        if 'snr' in data:
            snr = data['snr']
        if 'rsrq' in data:
            signal_quality = data['rsrq']
        if 'ecio' in data:
            snr = data['ecio']
        if 'sinr' in data:
            snr = data['sinr']
        if snr is not None:
            extra_values = {'snr': float(snr)}
        if signal_quality is not None:
            signal_quality = float(signal_quality)
        if snr is not None or signal_quality is not None:
            metric, created = Metric._get_or_create(
                object_id=pk,
                content_type=ct,
                configuration='signal_quality',
                name='signal quality',
                key=ifname,
            )
            metric.write(signal_quality, current, time=time, extra_values=extra_values)
            if created:
                self._create_signal_quality_chart(metric)
        # create access technology chart
        metric, created = Metric._get_or_create(
            object_id=pk,
            content_type=ct,
            configuration='access_tech',
            name='access technology',
            key=ifname,
        )
        metric.write(
            list(ACCESS_TECHNOLOGIES.keys()).index(access_type), current, time=time
        )
        if created:
            self._create_access_tech_chart(metric)

    def _write_cpu(
        self, load, cpus, primary_key, content_type, current=False, time=None
    ):
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
        metric.write(
            100 * float(load[0] / cpus), current, time=time, extra_values=extra_values
        )

    def _write_disk(
        self, disk_list, primary_key, content_type, current=False, time=None
    ):
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
        metric.write(100 * used_bytes / size_bytes, current, time=time)

    def _write_memory(
        self, memory, primary_key, content_type, current=False, time=None
    ):
        extra_values = {
            'total_memory': memory['total'],
            'free_memory': memory['free'],
            'buffered_memory': memory['buffered'],
            'shared_memory': memory['shared'],
        }
        if 'cached' in memory:
            extra_values['cached_memory'] = memory.get('cached')
        percent_used = 100 * (
            1 - (memory['free'] + memory['buffered']) / memory['total']
        )
        # Available Memory is not shown in some systems (older openwrt versions)
        if 'available' in memory:
            extra_values.update({'available_memory': memory['available']})
            if memory['available'] > memory['free']:
                percent_used = 100 * (
                    1 - (memory['available'] + memory['buffered']) / memory['total']
                )
        metric, created = Metric._get_or_create(
            object_id=primary_key, content_type=content_type, configuration='memory'
        )
        if created:
            self._create_resources_chart(metric, resource='memory')
            self._create_resources_alert_settings(metric, resource='memory')
        metric.write(percent_used, current, time=time, extra_values=extra_values)

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

    def _create_signal_strength_chart(self, metric):
        chart = Chart(metric=metric, configuration='signal_strength')
        chart.full_clean()
        chart.save()

    def _create_signal_quality_chart(self, metric):
        chart = Chart(metric=metric, configuration='signal_quality')
        chart.full_clean()
        chart.save()

    def _create_access_tech_chart(self, metric):
        chart = Chart(metric=metric, configuration='access_tech')
        chart.full_clean()
        chart.save()


device_metric = DeviceMetricView.as_view()


class MonitoringGeoJsonLocationList(GeoJsonLocationList):
    serializer_class = MonitoringGeoJsonLocationSerializer
    queryset = (
        Location.objects.filter(devicelocation__isnull=False)
        .annotate(
            device_count=Count('devicelocation'),
            ok_count=Count(
                'devicelocation',
                filter=Q(devicelocation__content_object__monitoring__status='ok'),
            ),
            problem_count=Count(
                'devicelocation',
                filter=Q(devicelocation__content_object__monitoring__status='problem'),
            ),
            critical_count=Count(
                'devicelocation',
                filter=Q(devicelocation__content_object__monitoring__status='critical'),
            ),
            unknown_count=Count(
                'devicelocation',
                filter=Q(devicelocation__content_object__monitoring__status='unknown'),
            ),
        )
        .order_by('-created')
    )


monitoring_geojson_location_list = MonitoringGeoJsonLocationList.as_view()


class MonitoringLocationDeviceList(LocationDeviceList):
    serializer_class = MonitoringDeviceSerializer

    def get_queryset(self):
        return super().get_queryset().select_related('monitoring').order_by('name')


monitoring_location_device_list = MonitoringLocationDeviceList.as_view()
