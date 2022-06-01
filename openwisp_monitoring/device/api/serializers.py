from rest_framework import serializers
from swapper import load_model

from openwisp_controller.geo.api.serializers import (
    GeoJsonLocationSerializer,
    LocationDeviceSerializer,
)
from openwisp_utils.api.serializers import ValidatedModelSerializer

DeviceMonitoring = load_model('device_monitoring', 'DeviceMonitoring')
WifiSession = load_model('device_monitoring', 'WifiSession')
WifiClient = load_model('device_monitoring', 'WifiClient')


class DeviceMonitoringSerializer(serializers.ModelSerializer):
    status_label = serializers.SerializerMethodField()

    def get_status_label(self, obj):
        return obj.get_status_display()

    class Meta:
        fields = ('status', 'status_label')
        model = DeviceMonitoring


class WifiClientSerializer(ValidatedModelSerializer):
    class Meta:
        fields = '__all__'
        model = WifiClient
        read_only_fields = (
            'created',
            'modified',
        )


class WifiSessionCreateUpdateSerializer(ValidatedModelSerializer):
    class Meta:
        model = WifiSession
        fields = ['device', 'wifi_client', 'ssid', 'interface_name']


class WifiSessionReadSerializer(ValidatedModelSerializer):
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


class MonitoringDeviceSerializer(LocationDeviceSerializer):
    monitoring = DeviceMonitoringSerializer()


class MonitoringGeoJsonLocationSerializer(GeoJsonLocationSerializer):
    ok_count = serializers.IntegerField()
    problem_count = serializers.IntegerField()
    critical_count = serializers.IntegerField()
    unknown_count = serializers.IntegerField()
