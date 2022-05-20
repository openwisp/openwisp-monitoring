from django.urls import include, path

urlpatterns = [
    path(
        '',
        include('openwisp_monitoring.device.api.urls', namespace='device_monitoring'),
    ),
    path(
        '', include('openwisp_monitoring.monitoring.api.urls', namespace='monitoring')
    ),
]
