from django.urls import path, re_path

from . import views

app_name = 'monitoring'

urlpatterns = [
    path(
        'api/v1/monitoring/device/',
        views.monitoring_device_list,
        name='api_monitoring_device_list',
    ),
    re_path(
        r'^api/v1/monitoring/device/(?P<pk>[^/]+)/$',
        views.device_metric,
        name='api_device_metric',
    ),
    re_path(
        r'^api/v1/monitoring/device/(?P<pk>[^/]+)/nearby-devices/$',
        views.monitoring_nearby_device_list,
        name='api_monitoring_nearby_device_list',
    ),
    path(
        'api/v1/monitoring/geojson/',
        views.monitoring_geojson_location_list,
        name='api_location_geojson',
    ),
    re_path(
        r'^api/v1/monitoring/location/(?P<pk>[^/]+)/device/$',
        views.monitoring_location_device_list,
        name='api_location_device_list',
    ),
    path(
        'api/v1/monitoring/wifi-session/',
        views.wifi_session_list,
        name='api_wifi_session_list',
    ),
    re_path(
        r'^api/v1/monitoring/wifi-session/(?P<pk>[^/]+)/$',
        views.wifi_session_detail,
        name='api_wifi_session_detail',
    ),
]
