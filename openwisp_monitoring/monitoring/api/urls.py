from django.urls import path

from . import views

app_name = 'monitoring_general'

urlpatterns = [
    path(
        'api/v1/monitoring/dashboard/',
        views.dashboard_timeseries,
        name='api_dashboard_timeseries',
    ),
]
