from django.urls import path, re_path

from . import views

app_name = 'monitoring'

urlpatterns = [
    re_path(
        r'^api/v1/monitoring/device/(?P<pk>[^/]+)/$',
        views.device_metric,
        name='api_device_metric',
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
    path(
        'api/v1/monitoring/wifi-client/',
        views.wifi_client_list,
        name='api_wifi_client_list',
    ),
    re_path(
        r'^api/v1/monitoring/wifi-client/(?P<pk>[^/]+)/$',
        views.wifi_client_detail,
        name='api_wifi_client_detail',
    ),
]
