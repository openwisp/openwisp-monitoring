from django.urls import path

from . import views


def get_api_urls(api_views=None):
    if api_views is None:
        api_views = views

    def get_view(name):
        return getattr(api_views, name, getattr(views, name))

    return [
        path(
            "api/v1/monitoring/device/",
            get_view("monitoring_device_list"),
            name="api_monitoring_device_list",
        ),
        path(
            "api/v1/monitoring/device/<uuid:pk>/metric/",
            get_view("device_metric_list"),
            name="api_device_metric_list",
        ),
        path(
            # uuid_any is registered by openwisp-controller
            "api/v1/monitoring/device/<uuid_any:pk>/",
            get_view("device_metric"),
            name="api_device_metric",
        ),
        path(
            "api/v1/monitoring/device/<uuid:pk>/nearby-devices/",
            get_view("monitoring_nearby_device_list"),
            name="api_monitoring_nearby_device_list",
        ),
        path(
            "api/v1/monitoring/geojson/",
            get_view("monitoring_geojson_location_list"),
            name="api_location_geojson",
        ),
        path(
            "api/v1/monitoring/location/<uuid:pk>/device/",
            get_view("monitoring_location_device_list"),
            name="api_location_device_list",
        ),
        path(
            "api/v1/monitoring/wifi-session/",
            get_view("wifi_session_list"),
            name="api_wifi_session_list",
        ),
        path(
            "api/v1/monitoring/wifi-session/<uuid:pk>/",
            get_view("wifi_session_detail"),
            name="api_wifi_session_detail",
        ),
        path(
            "api/v1/monitoring/location/<uuid:pk>/indoor-coordinates/",
            get_view("monitoring_indoor_coordinates_list"),
            name="api_indoor_coordinates_list",
        ),
    ]


app_name = "monitoring"
urlpatterns = get_api_urls()
