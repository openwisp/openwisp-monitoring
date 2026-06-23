from django.urls import path

from . import views

app_name = "monitoring"

urlpatterns = [
    path(
        "api/v1/monitoring/device/",
        views.monitoring_device_list,
        name="api_monitoring_device_list",
    ),
    path(
        "api/v1/monitoring/device/<uuid:pk>/metric/",
        views.device_metric_list,
        name="api_device_metric_list",
    ),
    path(
        "api/v1/monitoring/device/<uuid_any:pk>/",
        views.device_metric,
        name="api_device_metric",
    ),
    path(
        "api/v1/monitoring/device/<uuid:pk>/nearby-devices/",
        views.monitoring_nearby_device_list,
        name="api_monitoring_nearby_device_list",
    ),
    path(
        "api/v1/monitoring/geojson/",
        views.monitoring_geojson_location_list,
        name="api_location_geojson",
    ),
    path(
        "api/v1/monitoring/location/<uuid:pk>/device/",
        views.monitoring_location_device_list,
        name="api_location_device_list",
    ),
    path(
        "api/v1/monitoring/wifi-session/",
        views.wifi_session_list,
        name="api_wifi_session_list",
    ),
    path(
        "api/v1/monitoring/wifi-session/<uuid:pk>/",
        views.wifi_session_detail,
        name="api_wifi_session_detail",
    ),
    path(
        "api/v1/monitoring/location/<uuid:pk>/indoor-coordinates/",
        views.monitoring_indoor_coordinates_list,
        name="api_indoor_coordinates_list",
    ),
]
