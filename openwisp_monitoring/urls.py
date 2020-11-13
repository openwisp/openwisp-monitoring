from django.conf.urls import include, url

urlpatterns = [
    url(r'', include('openwisp_monitoring.device.api.urls', namespace='monitoring'))
]
