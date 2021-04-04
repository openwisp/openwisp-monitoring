from rest_framework import serializers
from swapper import load_model

from openwisp_controller.geo.api.serializers import (
    GeoJsonLocationSerializer,
    LocationDeviceSerializer,
)

DeviceMonitoring = load_model('device_monitoring', 'DeviceMonitoring')


class DeviceMonitoringSerializer(serializers.ModelSerializer):
    status_label = serializers.SerializerMethodField()

    def get_status_label(self, obj):
        return obj.get_status_display()

    class Meta:
        fields = ('status', 'status_label')
        model = DeviceMonitoring


class MonitoringDeviceSerializer(LocationDeviceSerializer):
    monitoring = DeviceMonitoringSerializer()


class MonitoringGeoJsonLocationSerializer(GeoJsonLocationSerializer):
    ok_count = serializers.IntegerField()
    problem_count = serializers.IntegerField()
    critical_count = serializers.IntegerField()
    unknown_count = serializers.IntegerField()
