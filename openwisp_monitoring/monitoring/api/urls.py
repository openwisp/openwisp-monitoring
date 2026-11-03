from django.urls import path

from . import views


def get_api_urls(api_views=None):
    if api_views is None:
        api_views = views

    def get_view(name):
        return getattr(api_views, name, getattr(views, name))

    return [
        path(
            "api/v1/monitoring/dashboard/",
            get_view("dashboard_timeseries"),
            name="api_dashboard_timeseries",
        ),
    ]


app_name = "monitoring_general"
urlpatterns = get_api_urls()
