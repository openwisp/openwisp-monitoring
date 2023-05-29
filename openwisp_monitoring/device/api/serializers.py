from rest_framework import serializers
from swapper import load_model

from openwisp_controller.config.api.serializers import DeviceListSerializer
from openwisp_controller.geo.api.serializers import (
    GeoJsonLocationSerializer,
    LocationDeviceSerializer,
)

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


class WifiClientSerializer(serializers.ModelSerializer):
    wifi6 = serializers.CharField(source='he', read_only=True)
    wifi5 = serializers.CharField(source='vht', read_only=True)
    wifi4 = serializers.CharField(source='ht', read_only=True)

    class Meta:
        model = WifiClient
        fields = [
            'mac_address',
            'vendor',
            'wifi6',
            'wifi5',
            'wifi4',
            'wmm',
            'wds',
            'wps',
        ]


class WifiSessionSerializer(serializers.ModelSerializer):
    client = WifiClientSerializer(source='wifi_client')
    organization = serializers.CharField(source='device.organization', read_only=True)
    device = serializers.CharField(source='device.name', read_only=True)

    class Meta:
        model = WifiSession
        fields = [
            'id',
            'organization',
            'device',
            'ssid',
            'interface_name',
            'client',
            'start_time',
            'stop_time',
            'modified',
        ]
