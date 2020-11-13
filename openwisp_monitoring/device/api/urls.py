from django.conf.urls import url

from . import views

app_name = 'monitoring'

urlpatterns = [
    url(
        r'^api/v1/monitoring/device/(?P<pk>[^/]+)/$',
        views.device_metric,
        name='api_device_metric',
    )
]
