from django.apps import AppConfig
from django.conf import settings
from django.db.models.signals import post_delete, post_save
from django.utils.translation import gettext_lazy as _
from swapper import get_model_name, load_model

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
        self.connect_metric_signals()

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

    def connect_metric_signals(self):
        from .api.views import DashboardTimeseriesView

        Metric = load_model('monitoring', 'Metric')
        Chart = load_model('monitoring', 'Chart')
        AlertSettings = load_model('monitoring', 'AlertSettings')
        post_delete.connect(
            Metric.post_delete_receiver,
            sender=Metric,
            dispatch_uid='metric_post_delete_receiver',
        )
        post_save.connect(
            Metric.invalidate_cache,
            sender=Metric,
            dispatch_uid='post_save_invalidate_metric_cache',
        )
        post_delete.connect(
            Metric.invalidate_cache,
            sender=Metric,
            dispatch_uid='post_delete_invalidate_metric_cache',
        )
        post_save.connect(
            AlertSettings.invalidate_cache,
            sender=AlertSettings,
            dispatch_uid='post_save_invalidate_metric_cache',
        )
        post_delete.connect(
            AlertSettings.invalidate_cache,
            sender=AlertSettings,
            dispatch_uid='post_delete_invalidate_metric_cache',
        )
        post_save.connect(
            DashboardTimeseriesView.invalidate_cache,
            sender=Metric,
            dispatch_uid='post_save_dashboard_tsdb_view_invalidate_cache',
        )
        post_save.connect(
            DashboardTimeseriesView.invalidate_cache,
            sender=Chart,
            dispatch_uid='post_save_dashboard_tsdb_view_invalidate_cache',
        )
        post_delete.connect(
            DashboardTimeseriesView.invalidate_cache,
            sender=Metric,
            dispatch_uid='post_delete_dashboard_tsdb_view_invalidate_cache',
        )
        post_delete.connect(
            DashboardTimeseriesView.invalidate_cache,
            sender=Chart,
            dispatch_uid='post_delete_dashboard_tsdb_view_invalidate_cache',
        )
