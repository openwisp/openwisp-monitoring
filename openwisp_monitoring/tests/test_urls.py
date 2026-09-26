from types import SimpleNamespace

from django.test import SimpleTestCase

from ..device.api import views as device_views
from ..device.api.urls import get_api_urls as get_device_api_urls
from ..monitoring.api import views as monitoring_views
from ..monitoring.api.urls import get_api_urls as get_monitoring_api_urls
from ..urls import get_urls


class TestApiUrls(SimpleTestCase):
    def test_device_api_urls_use_overrides_and_fallbacks(self):
        def custom_view(request):
            return None

        view_names = {
            "api_monitoring_device_list": "monitoring_device_list",
            "api_device_metric_list": "device_metric_list",
            "api_device_metric": "device_metric",
            "api_monitoring_nearby_device_list": "monitoring_nearby_device_list",
            "api_location_geojson": "monitoring_geojson_location_list",
            "api_location_device_list": "monitoring_location_device_list",
            "api_wifi_session_list": "wifi_session_list",
            "api_wifi_session_detail": "wifi_session_detail",
            "api_indoor_coordinates_list": "monitoring_indoor_coordinates_list",
        }

        custom_views = SimpleNamespace(device_metric=custom_view)

        callbacks = {
            pattern.name: pattern.callback
            for pattern in get_device_api_urls(custom_views)
        }

        for url_name, view_name in view_names.items():
            with self.subTest(url_name=url_name):
                expected = (
                    custom_view
                    if view_name == "device_metric"
                    else getattr(device_views, view_name)
                )
                self.assertIs(callbacks[url_name], expected)

    def test_monitoring_api_urls_use_overrides_and_fallbacks(self):
        def custom_view(request):
            return None

        custom_views = SimpleNamespace(dashboard_timeseries=custom_view)

        callbacks = {
            pattern.name: pattern.callback
            for pattern in get_monitoring_api_urls(custom_views)
        }

        self.assertIs(
            callbacks["api_dashboard_timeseries"],
            custom_view,
        )

        callbacks = {
            pattern.name: pattern.callback for pattern in get_monitoring_api_urls()
        }

        self.assertIs(
            callbacks["api_dashboard_timeseries"],
            monitoring_views.dashboard_timeseries,
        )

    def test_get_urls_uses_separate_api_view_modules(self):
        def custom_device_view(request):
            return None

        def custom_monitoring_view(request):
            return None

        custom_device_views = SimpleNamespace(device_metric=custom_device_view)
        custom_monitoring_views = SimpleNamespace(
            dashboard_timeseries=custom_monitoring_view
        )

        url_resolvers = {
            pattern.namespace: pattern for pattern in get_urls(custom_device_views)
        }

        device_callbacks = {
            pattern.name: pattern.callback
            for pattern in url_resolvers["monitoring"].url_patterns
        }
        monitoring_callbacks = {
            pattern.name: pattern.callback
            for pattern in url_resolvers["monitoring_general"].url_patterns
        }

        self.assertIs(
            device_callbacks["api_device_metric"],
            custom_device_view,
        )
        self.assertIs(
            monitoring_callbacks["api_dashboard_timeseries"],
            monitoring_views.dashboard_timeseries,
        )

        url_resolvers = {
            pattern.namespace: pattern
            for pattern in get_urls(
                monitoring_api_views=custom_monitoring_views,
            )
        }

        device_callbacks = {
            pattern.name: pattern.callback
            for pattern in url_resolvers["monitoring"].url_patterns
        }
        monitoring_callbacks = {
            pattern.name: pattern.callback
            for pattern in url_resolvers["monitoring_general"].url_patterns
        }

        self.assertIs(
            device_callbacks["api_device_metric"],
            device_views.device_metric,
        )
        self.assertIs(
            monitoring_callbacks["api_dashboard_timeseries"],
            custom_monitoring_view,
        )

    def test_get_urls_preserves_namespaces_and_url_names(self):
        expected_device_urls = {
            "api_monitoring_device_list",
            "api_device_metric_list",
            "api_device_metric",
            "api_monitoring_nearby_device_list",
            "api_location_geojson",
            "api_location_device_list",
            "api_wifi_session_list",
            "api_wifi_session_detail",
            "api_indoor_coordinates_list",
        }
        expected_monitoring_urls = {"api_dashboard_timeseries"}

        url_resolvers = {pattern.namespace: pattern for pattern in get_urls()}

        self.assertEqual(
            set(url_resolvers),
            {"monitoring", "monitoring_general"},
        )
        self.assertEqual(
            {pattern.name for pattern in url_resolvers["monitoring"].url_patterns},
            expected_device_urls,
        )
        self.assertEqual(
            {
                pattern.name
                for pattern in url_resolvers["monitoring_general"].url_patterns
            },
            expected_monitoring_urls,
        )
