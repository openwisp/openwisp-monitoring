from django.apps import AppConfig
from django.conf import settings
from django.db.models import Case, Count, Sum, When
from django.utils.translation import gettext_lazy as _
from swapper import get_model_name

from openwisp_utils.admin_theme import register_dashboard_chart
from openwisp_utils.admin_theme.menu import register_menu_group

from ..db import timeseries_db
from . import settings as app_settings
from .configuration import get_metric_configuration, register_metric_notifications


class MonitoringConfig(AppConfig):
    name = 'openwisp_monitoring.monitoring'
    label = 'monitoring'
    verbose_name = _('Network Monitoring')

    def ready(self):
        timeseries_db.create_database()
        setattr(settings, 'OPENWISP_ADMIN_SHOW_USERLINKS_BLOCK', True)
        metrics = get_metric_configuration()
        for metric_name, metric_config in metrics.items():
            register_metric_notifications(metric_name, metric_config)
        self.register_menu_groups()
        self.register_dashboard_items()

    def register_menu_groups(self):
        menu_group_config = {
            'label': 'Monitoring',
            'items': {
                2: {
                    'label': _('Metrics'),
                    'model': get_model_name('monitoring', 'Metric'),
                    'name': 'changelist',
                    'icon': 'ow-metrics',
                },
                3: {
                    'label': _('Checks'),
                    'model': get_model_name('check', 'Check'),
                    'name': 'changelist',
                    'icon': 'ow-monitoring-checks',
                },
            },
            'icon': 'ow-monitoring',
        }
        if app_settings.WIFI_SESSIONS_ENABLED:
            menu_group_config['items'].update(
                {
                    1: {
                        'label': _('WiFi Sessions'),
                        'model': get_model_name('monitoring', 'WiFiSession'),
                        'name': 'changelist',
                        'icon': 'ow-monitoring-checks',
                    },
                }
            )
        register_menu_group(
            position=80,
            config=menu_group_config,
        )

    def register_dashboard_items(self):
        if app_settings.WIFI_SESSIONS_ENABLED:
            register_dashboard_chart(
                position=6,
                config={
                    'name': _('Currently Active WiFi Sessions'),
                    'query_params': {
                        'app_label': 'monitoring',
                        'model': 'wifisession',
                        'annotate': {
                            'active': Count(
                                Case(
                                    When(
                                        stop_time__isnull=True,
                                        then=1,
                                    )
                                )
                            ),
                        },
                        'aggregate': {
                            'active__sum': Sum('active'),
                        },
                    },
                    'filters': {
                        'key': 'stop_time__isnull',
                        'active__sum': 'true',
                    },
                    'colors': {
                        'active__sum': '#267126',
                    },
                    'labels': {
                        'active__sum': _('Currently Active WiFi Sessions'),
                    },
                },
            )
