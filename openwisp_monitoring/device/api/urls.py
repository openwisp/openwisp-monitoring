from django.conf.urls import url

from . import views

app_name = 'monitoring'

urlpatterns = [
    url(
        r'^api/v1/monitoring/device/(?P<pk>[^/]+)/$',
        views.device_metric,
        name='api_device_metric',
    ),
    url(
        r'^api/v1/monitoring/geojson/$',
        views.monitoring_geojson_location_list,
        name='api_location_geojson',
    ),
    url(
        r'^api/v1/monitoring/location/(?P<pk>[^/]+)/device/$',
        views.monitoring_location_device_list,
        name='api_location_device_list',
    ),
]
