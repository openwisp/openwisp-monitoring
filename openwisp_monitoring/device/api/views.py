import logging
import uuid
from datetime import datetime

from cache_memoize import cache_memoize
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.db.models.functions import Distance
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.db.models.functions import Round
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import DjangoFilterBackend
from pytz import UTC
from rest_framework import pagination, serializers, status
from rest_framework.generics import (
    GenericAPIView,
    ListAPIView,
    RetrieveAPIView,
    get_object_or_404,
)
from rest_framework.permissions import SAFE_METHODS
from rest_framework.response import Response
from swapper import load_model

from openwisp_controller.config.api.views import DeviceListCreateView
from openwisp_controller.geo.api.views import (
    DevicePermission,
    GeoJsonLocationList,
    LocationDeviceList,
    ProtectedAPIMixin,
)
from openwisp_users.api.mixins import FilterByOrganizationManaged

from ...settings import CACHE_TIMEOUT
from ...views import MonitoringApiViewMixin
from ..schema import schema
from ..signals import device_metrics_received
from ..tasks import write_device_metrics
from .filters import (
    MonitoringDeviceFilter,
    MonitoringNearbyDeviceFilter,
    WifiSessionFilter,
)
from .serializers import (
    MonitoringDeviceDetailSerializer,
    MonitoringDeviceListSerializer,
    MonitoringGeoJsonLocationSerializer,
    MonitoringLocationDeviceSerializer,
    MonitoringNearbyDeviceSerializer,
    WifiSessionSerializer,
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


class ListViewPagination(pagination.PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


def get_device_args_rewrite(view, pk):
    """
    Use only the PK parameter for calculating the cache key
    """
    try:
        pk = uuid.UUID(pk)
    except ValueError:
        return pk
    return pk.hex


def get_charts_args_rewrite(view, request, pk):
    return (pk,)


class DeviceKeyAuthenticationMixin(object):
    def get_permissions(self):
        if self.request.method in SAFE_METHODS and not self.request.query_params.get(
            'key'
        ):
            self.permission_classes = ProtectedAPIMixin.permission_classes
        return super().get_permissions()

    def get_authenticators(self):
        if self.request.method in SAFE_METHODS and not self.request.GET.get('key'):
            self.authentication_classes = ProtectedAPIMixin.authentication_classes
        return super().get_authenticators()


class DeviceMetricView(
    DeviceKeyAuthenticationMixin, MonitoringApiViewMixin, GenericAPIView
):
    """
    Retrieve device information, monitoring status (health status),
    a list of metrics, chart data and
    optionally device status information (if ``?status=true``).

    Suports session authentication, token authentication,
    or alternatively device key authentication passed as query
    string parameter (this method is meant to be used by network devices).
    """

    model = DeviceData
    queryset = (
        DeviceData.objects.filter(organization__is_active=True)
        .only(
            'id',
            'key',
        )
        .all()
    )
    serializer_class = serializers.Serializer
    permission_classes = [DevicePermission]
    schema = schema

    @classmethod
    def invalidate_get_device_cache(cls, instance, **kwargs):
        """
        Called from signal receiver which performs cache invalidation
        """
        view = cls()
        view.get_object.invalidate(view, str(instance.pk))
        logger.debug(f'invalidated view cache for device ID {instance.pk}')

    @classmethod
    def invalidate_get_charts_cache(cls, instance, *args, **kwargs):
        if isinstance(instance, Device):
            pk = instance.id
        elif isinstance(instance, Metric):
            pk = instance.object_id
        elif isinstance(instance, Chart):
            pk = instance.metric.object_id
        cls._get_charts.invalidate(None, None, pk)

    def get(self, request, pk):
        # ensure valid UUID
        try:
            pk = str(uuid.UUID(pk))
        except ValueError:
            return Response({'detail': 'not found'}, status=404)
        self.instance = self.get_object(pk)
        response = super().get(request, pk)
        if not request.query_params.get('csv'):
            charts_data = dict(response.data)
            device_metrics_data = MonitoringDeviceDetailSerializer(self.instance).data
            return Response(
                {**device_metrics_data, **charts_data}, status=status.HTTP_200_OK
            )
        return response

    @cache_memoize(CACHE_TIMEOUT, args_rewrite=get_charts_args_rewrite)
    def _get_charts(self, request, *args, **kwargs):
        ct = ContentType.objects.get_for_model(Device)
        return Chart.objects.filter(
            metric__object_id=args[0], metric__content_type_id=ct.id
        ).select_related('metric')

    def _get_additional_data(self, request, *args, **kwargs):
        if request.query_params.get('status', False):
            return {'data': self.instance.data}
        return {}

    @cache_memoize(CACHE_TIMEOUT, args_rewrite=get_device_args_rewrite)
    def get_object(self, pk):
        return super().get_object()

    def post(self, request, pk):
        self.instance = self.get_object(pk)
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
            str(self.instance.pk), self.instance.data, time=time_obj, current=current
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
    serializer_class = MonitoringLocationDeviceSerializer

    def get_queryset(self):
        return super().get_queryset().select_related('monitoring').order_by('name')


monitoring_location_device_list = MonitoringLocationDeviceList.as_view()


class MonitoringNearbyDeviceList(
    DeviceKeyAuthenticationMixin, FilterByOrganizationManaged, ListAPIView
):
    serializer_class = MonitoringNearbyDeviceSerializer
    pagination_class = ListViewPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = MonitoringNearbyDeviceFilter
    permission_classes = []

    def get_queryset(self):
        qs = Device.objects.select_related('monitoring')
        location_lookup = Q(devicelocation__content_object_id=self.kwargs['pk'])
        device_key = self.request.query_params.get('key')
        if device_key:
            location_lookup &= Q(devicelocation__content_object__key=device_key)
        if not self.request.user.is_superuser and not device_key:
            qs = self.get_organization_queryset(qs)
        location = get_object_or_404(Location.objects, location_lookup)
        return (
            qs.exclude(id=self.kwargs['pk'])
            .filter(
                devicelocation__isnull=False,
            )
            .annotate(
                distance=Round(
                    Distance('devicelocation__location__geometry', location.geometry)
                )
            )
            .order_by('distance')
        )


monitoring_nearby_device_list = MonitoringNearbyDeviceList.as_view()


class MonitoringDeviceList(DeviceListCreateView):
    """
    Lists devices and their monitoring status (health status).

    Supports session authentication and token authentication.

    `NOTE:` The response does not include the information and
    health status of the specific metrics, this information
    can be retrieved in the detail endpoint of each device.
    """

    serializer_class = MonitoringDeviceListSerializer
    http_method_names = ['get', 'head', 'options']
    filter_backends = [DjangoFilterBackend]
    filterset_class = MonitoringDeviceFilter

    def get_queryset(self):
        return super().get_queryset().select_related('monitoring').order_by('name')


monitoring_device_list = MonitoringDeviceList.as_view()


class WifiSessionListView(ProtectedAPIMixin, FilterByOrganizationManaged, ListAPIView):
    queryset = WifiSession.objects.select_related(
        'device', 'wifi_client', 'device__organization', 'device__group'
    )
    organization_field = 'device__organization'
    filter_backends = [DjangoFilterBackend]
    pagination_class = ListViewPagination
    filterset_class = WifiSessionFilter
    serializer_class = WifiSessionSerializer


wifi_session_list = WifiSessionListView.as_view()


class WifiSessionDetailView(
    ProtectedAPIMixin, FilterByOrganizationManaged, RetrieveAPIView
):
    queryset = WifiSession.objects.select_related(
        'device', 'wifi_client', 'device__organization'
    )
    organization_field = 'device__organization'
    serializer_class = WifiSessionSerializer


wifi_session_detail = WifiSessionDetailView.as_view()
