from django.urls import include, path

from .device.api.urls import get_api_urls as get_device_api_urls
from .monitoring.api.urls import get_api_urls as get_monitoring_api_urls


def get_urls(device_api_views=None, monitoring_api_views=None):
    return [
        path(
            "",
            include(
                (get_device_api_urls(device_api_views), "monitoring"),
                namespace="monitoring",
            ),
        ),
        # The following endpoint was developed after "openwisp_monitoring.device.api"
        # which already used the "monitoring" namespace. The "monitoring_general"
        # namespace is used below to avoid changing the old naming scheme and
        # maintain backward compatibility.
        path(
            "",
            include(
                (get_monitoring_api_urls(monitoring_api_views), "monitoring_general"),
                namespace="monitoring_general",
            ),
        ),
    ]


urlpatterns = get_urls()
