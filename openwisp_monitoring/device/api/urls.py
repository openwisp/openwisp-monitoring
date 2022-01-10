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
]
