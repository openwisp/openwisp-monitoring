from rest_framework import serializers
from swapper import load_model

from openwisp_controller.config.api.serializers import DeviceListSerializer
from openwisp_controller.geo.api.serializers import (
    GeoJsonLocationSerializer,
    LocationDeviceSerializer,
)
from openwisp_users.api.mixins import FilterSerializerByOrgManaged
from openwisp_utils.api.serializers import ValidatedModelSerializer

Device = load_model('config', 'Device')
DeviceMonitoring = load_model('device_monitoring', 'DeviceMonitoring')
Device = load_model('config', 'Device')
WifiSession = load_model('device_monitoring', 'WifiSession')
WifiClient = load_model('device_monitoring', 'WifiClient')


class BaseDeviceMonitoringSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceMonitoring
        fields = ('status',)


class DeviceMonitoringLocationSerializer(BaseDeviceMonitoringSerializer):
    status_label = serializers.SerializerMethodField()

    def get_status_label(self, obj):
        return obj.get_status_display()

    class Meta(BaseDeviceMonitoringSerializer.Meta):
        fields = BaseDeviceMonitoringSerializer.Meta.fields + ('status_label',)


class DeviceMonitoringSerializer(BaseDeviceMonitoringSerializer):
    related_metrics = serializers.SerializerMethodField()

    def get_related_metrics(self, obj):
        return obj.related_metrics.values('name', 'is_healthy').order_by('name')

    class Meta(BaseDeviceMonitoringSerializer.Meta):
        fields = BaseDeviceMonitoringSerializer.Meta.fields + ('related_metrics',)


class MonitoringLocationDeviceSerializer(LocationDeviceSerializer):
    monitoring = DeviceMonitoringLocationSerializer()


class MonitoringDeviceListSerializer(DeviceListSerializer):
    monitoring = BaseDeviceMonitoringSerializer(read_only=True)

    def get_status(self, obj):
        return obj.get_status_display()

    class Meta:
        model = Device
        fields = [
            'id',
            'name',
            'organization',
            'group',
            'mac_address',
            'key',
            'last_ip',
            'management_ip',
            'model',
            'os',
            'system',
            'notes',
            'config',
            'monitoring',
            'created',
            'modified',
        ]


class MonitoringDeviceDetailSerializer(MonitoringDeviceListSerializer):
    monitoring = DeviceMonitoringSerializer(read_only=True)


class MonitoringGeoJsonLocationSerializer(GeoJsonLocationSerializer):
    ok_count = serializers.IntegerField()
    problem_count = serializers.IntegerField()
    critical_count = serializers.IntegerField()
    unknown_count = serializers.IntegerField()


class WifiClientSerializer(FilterSerializerByOrgManaged, ValidatedModelSerializer):
    class Meta:
        model = WifiClient
        fields = [
            'mac_address',
            'vendor',
            'ht',
            'vht',
            'wmm',
            'wds',
            'wps',
            'modified',
            'created',
        ]
        read_only_fields = (
            'created',
            'modified',
        )


class WifiSessionSerializer(FilterSerializerByOrgManaged, ValidatedModelSerializer):
    client = WifiClientSerializer(source='wifi_client')
    device_name = serializers.CharField(source='device.name', read_only=True)
    organization_id = serializers.CharField(
        source='device.organization.id', read_only=True
    )
    organization_name = serializers.CharField(
        source='device.organization', read_only=True
    )

    class Meta:
        model = WifiSession
        fields = [
            'id',
            'device_name',
            'device',
            'organization_name',
            'organization_id',
            'client',
            'ssid',
            'interface_name',
            'start_time',
            'stop_time',
            'modified',
        ]
        read_only_fields = ('stop_time', 'modified')
