from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from swapper import load_model

from openwisp_controller.geo.api.serializers import (
    GeoJsonLocationSerializer,
    LocationDeviceSerializer,
)
from openwisp_users.api.mixins import FilterSerializerByOrgManaged
from openwisp_utils.api.serializers import ValidatedModelSerializer

DeviceMonitoring = load_model('device_monitoring', 'DeviceMonitoring')
Device = load_model('config', 'Device')
WifiSession = load_model('device_monitoring', 'WifiSession')
WifiClient = load_model('device_monitoring', 'WifiClient')


class DeviceMonitoringSerializer(serializers.ModelSerializer):
    status_label = serializers.SerializerMethodField()

    def get_status_label(self, obj):
        return obj.get_status_display()

    class Meta:
        fields = ('status', 'status_label')
        model = DeviceMonitoring


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


class WifiSessionCreateUpdateSerializer(
    FilterSerializerByOrgManaged, ValidatedModelSerializer
):
    class Meta:
        model = WifiSession
        fields = ['device', 'wifi_client', 'ssid', 'interface_name']
        # When a relationship or ChoiceField has too many items,
        # rendering the widget containing all the options can become very slow,
        # and cause the browsable API rendering to perform poorly, Changed select field to input.
        extra_kwargs = {
            'device': {'style': {'base_template': 'input.html'}},
            'wifi_client': {'style': {'base_template': 'input.html'}},
        }

    def validate_device(self, device):
        user = self.context['request'].user
        if user and not user.is_manager(device.organization_id):
            raise serializers.ValidationError(
                _('Device organization must be in user managed organization')
            )
        return device


class WifiSessionReadSerializer(FilterSerializerByOrgManaged, ValidatedModelSerializer):
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
