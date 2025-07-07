from rest_framework import serializers
from swapper import load_model

from openwisp_controller.config.api.serializers import DeviceListSerializer
from openwisp_controller.geo.api.serializers import (
    GeoJsonLocationSerializer,
    LocationDeviceSerializer,
)
from openwisp_users.api.mixins import FilterSerializerByOrgManaged

Device = load_model("config", "Device")
DeviceMonitoring = load_model("device_monitoring", "DeviceMonitoring")
DeviceData = load_model("device_monitoring", "DeviceData")
Device = load_model("config", "Device")
WifiSession = load_model("device_monitoring", "WifiSession")
WifiClient = load_model("device_monitoring", "WifiClient")


class BaseDeviceMonitoringSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceMonitoring
        fields = ("status",)


class DeviceMonitoringLocationSerializer(BaseDeviceMonitoringSerializer):
    status_label = serializers.SerializerMethodField()

    def get_status_label(self, obj):
        return obj.get_status_display()

    class Meta(BaseDeviceMonitoringSerializer.Meta):
        fields = BaseDeviceMonitoringSerializer.Meta.fields + ("status_label",)


class DeviceMonitoringSerializer(BaseDeviceMonitoringSerializer):
    related_metrics = serializers.SerializerMethodField()

    def get_related_metrics(self, obj):
        return obj.related_metrics.values("name", "is_healthy").order_by("name")

    class Meta(BaseDeviceMonitoringSerializer.Meta):
        fields = BaseDeviceMonitoringSerializer.Meta.fields + ("related_metrics",)


class MonitoringLocationDeviceSerializer(LocationDeviceSerializer):
    monitoring = DeviceMonitoringLocationSerializer()


class MonitoringNearbyDeviceSerializer(
    FilterSerializerByOrgManaged, serializers.ModelSerializer
):
    monitoring_status = serializers.CharField(source="monitoring.status")
    distance = serializers.SerializerMethodField("get_distance")
    monitoring_data = serializers.SerializerMethodField("get_monitoring_data")

    class Meta(DeviceListSerializer.Meta):
        model = Device
        fields = [
            "id",
            "name",
            "organization",
            "group",
            "mac_address",
            "management_ip",
            "model",
            "os",
            "system",
            "notes",
            "distance",
            "monitoring_status",
            "monitoring_data",
        ]

    def get_distance(self, obj):
        return obj.distance.m

    def get_monitoring_data(self, obj):
        return DeviceData.objects.only("id").get(id=obj.id).data


class MonitoringDeviceListSerializer(DeviceListSerializer):
    monitoring = BaseDeviceMonitoringSerializer(read_only=True)

    def get_status(self, obj):
        return obj.get_status_display()

    class Meta:
        model = Device
        fields = [
            "id",
            "name",
            "organization",
            "group",
            "mac_address",
            "key",
            "last_ip",
            "management_ip",
            "model",
            "os",
            "system",
            "notes",
            "config",
            "monitoring",
            "created",
            "modified",
        ]


class MonitoringDeviceDetailSerializer(MonitoringDeviceListSerializer):
    monitoring = DeviceMonitoringSerializer(read_only=True)


class MonitoringGeoJsonLocationSerializer(GeoJsonLocationSerializer):
    ok_count = serializers.IntegerField()
    problem_count = serializers.IntegerField()
    critical_count = serializers.IntegerField()
    unknown_count = serializers.IntegerField()


class WifiClientSerializer(serializers.ModelSerializer):
    wifi6 = serializers.CharField(source="he", read_only=True)
    wifi5 = serializers.CharField(source="vht", read_only=True)
    wifi4 = serializers.CharField(source="ht", read_only=True)

    class Meta:
        model = WifiClient
        fields = [
            "mac_address",
            "vendor",
            "wifi6",
            "wifi5",
            "wifi4",
            "wmm",
            "wds",
            "wps",
        ]


class WifiSessionSerializer(serializers.ModelSerializer):
    client = WifiClientSerializer(source="wifi_client")
    organization = serializers.CharField(source="device.organization", read_only=True)
    device = serializers.CharField(source="device.name", read_only=True)

    class Meta:
        model = WifiSession
        fields = [
            "id",
            "organization",
            "device",
            "ssid",
            "interface_name",
            "client",
            "start_time",
            "stop_time",
            "modified",
        ]


class NetJSONDeviceNodeSerializer(serializers.ModelSerializer):
    """Serialize a single device as a NetJSON *node* object used by the
    device map. The serializer flattens the relevant information required by
    the frontend clustering logic:

    * ``id``: string representation of the device UUID
    * ``name``: device name (used as the node label on the map)
    * ``location``: ``{"lat": float, "lng": float}`` extracted from the
      related ``DeviceLocation`` geometry (lat = Y, lng = X)
    * ``properties``: arbitrary object – it now includes the monitoring
      ``status`` (for clustering), the ``location`` (lat/lng pair used by the
      map renderer) and ``location_id`` (primary key of the related
      ``DeviceLocation`` for popup URLs).
    """

    location = serializers.SerializerMethodField()
    # attach arbitrary properties (currently only status)
    properties = serializers.SerializerMethodField()

    class Meta:
        model = Device
        fields = ("id", "name", "location", "properties")

    # ---------------------------------------------------------------------
    # Helper methods
    # ---------------------------------------------------------------------
    def get_location(self, obj):
        loc = getattr(obj, "devicelocation", None)
        if loc and getattr(loc, "location", None):
            point = loc.location
            if hasattr(point, "geometry"):
                point = point.geometry

            if hasattr(point, "y") and hasattr(point, "x"):
                # Standard GeoDjango Point object
                return {"lat": point.y, "lng": point.x}
            lat = getattr(point, "lat", None) or getattr(point, "latitude", None)
            lng = getattr(point, "lng", None) or getattr(point, "longitude", None)
            if lat is not None and lng is not None:
                return {"lat": lat, "lng": lng}
            return None
        return None

    def get_properties(self, obj):
        loc_pk = getattr(getattr(obj, "devicelocation", None), "pk", None)
        location = self.get_location(obj)
        props = {"status": obj.monitoring.status, "location_id": loc_pk}
        if location:
            props["location"] = location
        return props
