import logging
import uuid
from datetime import datetime

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django_filters import rest_framework as filters
from django_filters.rest_framework import DjangoFilterBackend
from pytz import UTC
from rest_framework import pagination, serializers, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.generics import (
    GenericAPIView,
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.permissions import SAFE_METHODS
from rest_framework.response import Response
from swapper import load_model

from openwisp_controller.geo.api.views import (
    DevicePermission,
    GeoJsonLocationList,
    LocationDeviceList,
)
from openwisp_users.api.authentication import BearerAuthentication
from openwisp_users.api.mixins import FilterByOrganizationManaged
from openwisp_users.api.permissions import DjangoModelPermissions, IsOrganizationManager

from ...views import MonitoringApiViewMixin
from ..schema import schema
from ..signals import device_metrics_received
from ..tasks import write_device_metrics
from .serializers import (
    MonitoringDeviceSerializer,
    MonitoringGeoJsonLocationSerializer,
    WifiClientSerializer,
    WifiSessionCreateUpdateSerializer,
    WifiSessionReadSerializer,
)

logger = logging.getLogger(__name__)
Chart = load_model('monitoring', 'Chart')
Metric = load_model('monitoring', 'Metric')
AlertSettings = load_model('monitoring', 'AlertSettings')
Device = load_model('config', 'Device')
DeviceMonitoring = load_model('device_monitoring', 'DeviceMonitoring')
DeviceData = load_model('device_monitoring', 'DeviceData')
Location = load_model('geo', 'Location')
WifiSession = load_model('device_monitoring', 'WifiSession')
WifiClient = load_model('device_monitoring', 'WifiClient')


class ListViewPagination(pagination.PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class WifiSessionProtectedAPIMixin(FilterByOrganizationManaged):
    authentication_classes = [BearerAuthentication, SessionAuthentication]
    permission_classes = list(FilterByOrganizationManaged.permission_classes) + [
        IsOrganizationManager,
        DjangoModelPermissions,
    ]


class WifiClientProtectedAPIMixin(FilterByOrganizationManaged):
    authentication_classes = [BearerAuthentication, SessionAuthentication]
    permission_classes = list(FilterByOrganizationManaged.permission_classes) + [
        DjangoModelPermissions,
    ]


class DeviceMetricView(MonitoringApiViewMixin, GenericAPIView):
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
        return super().get(request, pk)

    def _get_charts(self, request, *args, **kwargs):
        ct = ContentType.objects.get_for_model(Device)
        return Chart.objects.filter(
            metric__object_id=args[0], metric__content_type=ct
        ).select_related('metric')

    def _get_additional_data(self, request, *args, **kwargs):
        if request.query_params.get('status', False):
            return {'data': self.instance.data}
        return {}

    def post(self, request, pk):
        self.instance = self.get_object()
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
        # writing data is intensive, let's pass that to the background workers
        write_device_metrics.delay(
            self.instance.pk, self.instance.data, time=time_obj, current=current
        )
        device_metrics_received.send(
            sender=self.model,
            instance=self.instance,
            request=request,
            time=time,
            current=current,
        )
        return Response(None)


device_metric = DeviceMetricView.as_view()


class WifiSessionFilter(filters.FilterSet):
    organization_slug = filters.CharFilter(
        field_name='device__organization__slug', label='Organization slug'
    )

    class Meta:
        model = WifiSession
        fields = {
            'device': ['exact'],
            'device__group': ['exact'],
            'start_time': ['exact', 'gt', 'gte', 'lt', 'lte'],
            'stop_time': ['exact', 'gt', 'gte', 'lt', 'lte'],
        }


class WifiSessionListCreateView(WifiSessionProtectedAPIMixin, ListCreateAPIView):
    queryset = WifiSession.objects.select_related(
        'device', 'wifi_client', 'device__organization', 'device__group'
    )
    organization_field = 'device__organization'
    filter_backends = [DjangoFilterBackend]
    pagination_class = ListViewPagination
    filterset_class = WifiSessionFilter

    def get_serializer_class(self):
        if self.request.method in SAFE_METHODS:
            return WifiSessionReadSerializer
        return WifiSessionCreateUpdateSerializer


wifi_session_list = WifiSessionListCreateView.as_view()


class WifiSessionDetailView(WifiSessionProtectedAPIMixin, RetrieveUpdateDestroyAPIView):
    queryset = WifiSession.objects.select_related(
        'device', 'wifi_client', 'device__organization'
    )
    organization_field = 'device__organization'

    def get_serializer_class(self):
        if self.request.method in SAFE_METHODS:
            return WifiSessionReadSerializer
        return WifiSessionCreateUpdateSerializer


wifi_session_detail = WifiSessionDetailView.as_view()


class WifiClientListCreateView(WifiClientProtectedAPIMixin, ListCreateAPIView):
    serializer_class = WifiClientSerializer
    queryset = WifiClient.objects.all()
    filter_backends = [DjangoFilterBackend]
    pagination_class = ListViewPagination
    filterset_fields = ['vendor']
    organization_field = 'wifisession__device__organization'

    def get_permissions(self):
        if self.request.method in ['GET']:
            self.permission_classes = WifiClientProtectedAPIMixin.permission_classes + [
                IsOrganizationManager
            ]
        return [permission() for permission in self.permission_classes]


wifi_client_list = WifiClientListCreateView.as_view()


class WifiClientDetailView(WifiClientProtectedAPIMixin, RetrieveUpdateDestroyAPIView):
    serializer_class = WifiClientSerializer
    queryset = WifiClient.objects.all()
    organization_field = 'wifisession__device__organization'


wifi_client_detail = WifiClientDetailView.as_view()


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
