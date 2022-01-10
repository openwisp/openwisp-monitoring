from django.urls import include, path

urlpatterns = [
    path('', include('openwisp_monitoring.device.api.urls', namespace='monitoring'))
]
