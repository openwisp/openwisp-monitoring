from django.apps import AppConfig
from django.conf import settings
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from swapper import get_model_name

from openwisp_utils.admin_theme.dashboard import register_dashboard_template
from openwisp_utils.admin_theme.menu import register_menu_group

from ..db import timeseries_db
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
        self.register_dashboard_templates()

    def register_menu_groups(self):
        register_menu_group(
            position=80,
            config={
                'label': 'Monitoring',
                'items': {
                    1: {
                        'label': _('Metrics'),
                        'model': get_model_name('monitoring', 'Metric'),
                        'name': 'changelist',
                        'icon': 'ow-metrics',
                    },
                    2: {
                        'label': _('Checks'),
                        'model': get_model_name('check', 'Check'),
                        'name': 'changelist',
                        'icon': 'ow-monitoring-checks',
                    },
                },
                'icon': 'ow-monitoring',
            },
        )

    def register_dashboard_templates(self):
        register_dashboard_template(
            position=55,
            config={
                'template': 'monitoring/paritals/chart.html',
                'css': (
                    'monitoring/css/percircle.min.css',
                    'monitoring/css/chart.css',
                    'monitoring/css/dashboard-chart.css',
                ),
                'js': (
                    'monitoring/js/percircle.min.js',
                    'monitoring/js/chart.js',
                    'monitoring/js/chart-utils.js',
                    'monitoring/js/dashboard-chart.js',
                ),
            },
            extra_config={
                'api_url': reverse_lazy('monitoring_general:api_dashboard_timeseries'),
            },
        )
