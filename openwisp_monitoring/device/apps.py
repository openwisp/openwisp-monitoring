from urllib.parse import urljoin

from django.apps import AppConfig
from django.conf import settings
from django.core.cache import cache
from django.db.models import Count
from django.db.models.signals import post_delete, post_save
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from swapper import get_model_name, load_model

from openwisp_controller.config.signals import checksum_requested, config_status_changed
from openwisp_controller.connection import settings as connection_settings
from openwisp_controller.connection.signals import is_working_changed
from openwisp_utils.admin_theme import (
    register_dashboard_chart,
    register_dashboard_template,
)
from openwisp_utils.admin_theme.menu import register_menu_subitem

from ..check import settings as check_settings
from ..monitoring.signals import threshold_crossed
from ..settings import MONITORING_API_BASEURL, MONITORING_API_URLCONF
from ..utils import transaction_on_commit
from . import settings as app_settings
from .signals import device_metrics_received, health_status_changed
from .utils import (
    get_device_cache_key,
    manage_default_retention_policy,
    manage_short_retention_policy,
)


class DeviceMonitoringConfig(AppConfig):
    name = 'openwisp_monitoring.device'
    label = 'device_monitoring'
    verbose_name = _('Device Monitoring')

    def ready(self):
        manage_default_retention_policy()
        manage_short_retention_policy()
        self.connect_is_working_changed()
        self.connect_device_signals()
        self.connect_config_status_changed()
        self.connect_wifi_client_signals()
        self.connect_offline_device_close_wifisession()
        self.connect_check_signals()
        self.device_recovery_detection()
        self.set_update_config_model()
        self.register_dashboard_items()
        self.register_menu_groups()
        self.add_connection_ignore_notification_reasons()

    def connect_check_signals(self):
        from django.db.models.signals import post_delete, post_save
        from swapper import load_model

        Check = load_model('check', 'Check')
        DeviceMonitoring = load_model('device_monitoring', 'DeviceMonitoring')

        post_save.connect(
            DeviceMonitoring.handle_critical_metric,
            sender=Check,
            dispatch_uid='check_post_save_receiver',
        )
        post_delete.connect(
            DeviceMonitoring.handle_critical_metric,
            sender=Check,
            dispatch_uid='check_post_delete_receiver',
        )

    def connect_device_signals(self):
        from .api.views import DeviceMetricView

        Device = load_model('config', 'Device')
        DeviceData = load_model('device_monitoring', 'DeviceData')
        DeviceLocation = load_model('geo', 'DeviceLocation')
        Metric = load_model('monitoring', 'Metric')
        Chart = load_model('monitoring', 'Chart')
        Organization = load_model('openwisp_users', 'Organization')

        post_save.connect(
            self.device_post_save_receiver,
            sender=Device,
            dispatch_uid='device_post_save_receiver',
        )
        post_save.connect(
            DeviceData.invalidate_cache,
            sender=Device,
            dispatch_uid='post_save_device_invalidate_devicedata_cache',
        )
        post_save.connect(
            DeviceData.invalidate_cache,
            sender=DeviceLocation,
            dispatch_uid='post_save_devicelocation_invalidate_devicedata_cache',
        )
        post_save.connect(
            DeviceMetricView.invalidate_get_charts_cache,
            sender=Metric,
            dispatch_uid=('metric_post_save_invalidate_view_charts_cache'),
        )
        post_save.connect(
            DeviceMetricView.invalidate_get_charts_cache,
            sender=Chart,
            dispatch_uid=('chart_post_save_invalidate_view_charts_cache'),
        )

        post_delete.connect(
            self.device_post_delete_receiver,
            sender=Device,
            dispatch_uid='device_post_delete_receiver',
        )
        post_delete.connect(
            DeviceMetricView.invalidate_get_device_cache,
            sender=Device,
            dispatch_uid=('device_post_delete_invalidate_view_device_cache'),
        )
        post_delete.connect(
            DeviceMetricView.invalidate_get_charts_cache,
            sender=Device,
            dispatch_uid=('device_post_delete_invalidate_view_charts_cache'),
        )
        post_delete.connect(
            DeviceMetricView.invalidate_get_charts_cache,
            sender=Metric,
            dispatch_uid=('metric_post_delete_invalidate_view_charts_cache'),
        )
        post_delete.connect(
            DeviceMetricView.invalidate_get_charts_cache,
            sender=Chart,
            dispatch_uid=('chart_post_delete_invalidate_view_charts_cache'),
        )
        post_delete.connect(
            DeviceData.invalidate_cache,
            sender=Device,
            dispatch_uid='post_delete_device_invalidate_devicedata_cache',
        )
        post_delete.connect(
            DeviceData.invalidate_cache,
            sender=DeviceLocation,
            dispatch_uid='post_delete_devicelocation_invalidate_devicedata_cache',
        )
        post_save.connect(
            self.organization_post_save_receiver,
            sender=Organization,
            dispatch_uid='post_save_organization_disabled_monitoring',
        )

    @classmethod
    def device_post_save_receiver(cls, instance, created, **kwargs):
        if created:
            DeviceMonitoring = load_model('device_monitoring', 'DeviceMonitoring')
            DeviceMonitoring.objects.create(device=instance)

    @classmethod
    def device_post_delete_receiver(cls, instance, **kwargs):
        DeviceData = load_model('device_monitoring', 'DeviceData')
        instance.__class__ = DeviceData
        instance.checks.all().delete()
        instance.metrics.all().delete()

    @classmethod
    def organization_post_save_receiver(cls, instance, *args, **kwargs):
        if instance.is_active is False:
            from .tasks import handle_disabled_organization

            handle_disabled_organization.delay(str(instance.id))

    def device_recovery_detection(self):
        if not app_settings.DEVICE_RECOVERY_DETECTION:
            return

        Device = load_model('config', 'Device')
        DeviceData = load_model('device_monitoring', 'DeviceData')
        DeviceMonitoring = load_model('device_monitoring', 'DeviceMonitoring')
        health_status_changed.connect(
            self.manage_device_recovery_cache_key,
            sender=DeviceMonitoring,
            dispatch_uid='recovery_health_status_changed',
        )
        checksum_requested.connect(
            self.trigger_device_recovery_checks,
            sender=Device,
            dispatch_uid='recovery_checksum_requested',
        )
        device_metrics_received.connect(
            self.trigger_device_recovery_checks,
            sender=DeviceData,
            dispatch_uid='recovery_device_metrics_received',
        )

    @classmethod
    def manage_device_recovery_cache_key(cls, instance, status, **kwargs):
        """
        It sets the ``cache_key`` as 1 when device ``health_status`` goes to ``critical``
        and deletes the ``cache_key`` when device recovers from ``critical`` state
        """
        cache_key = get_device_cache_key(device=instance.device)
        if status == 'critical':
            cache.set(cache_key, 1, timeout=None)
        else:
            cache.delete(cache_key)

    @classmethod
    def trigger_device_recovery_checks(cls, instance, **kwargs):
        from .tasks import trigger_device_checks

        # Cache is managed by "manage_device_recovery_cache_key".
        if cache.get(get_device_cache_key(device=instance), False):
            transaction_on_commit(lambda: trigger_device_checks.delay(pk=instance.pk))

    @classmethod
    def connect_is_working_changed(cls):
        is_working_changed.connect(
            cls.is_working_changed_receiver,
            sender=load_model('connection', 'DeviceConnection'),
            dispatch_uid='is_working_changed_monitoring',
        )

    @classmethod
    def is_working_changed_receiver(
        cls, instance, is_working, old_is_working, failure_reason, **kwargs
    ):
        from .tasks import trigger_device_checks

        Check = load_model('check', 'Check')
        device = instance.device
        device_monitoring = device.monitoring
        # if old_is_working is None, it's a new device connection which wasn't
        # ever used yet, so nothing is really changing and we don't need to do anything
        if old_is_working is None and is_working:
            return
        # if device is down because of connectivity issues, it's probably due
        # to reboot caused by firmware upgrade, avoid notifications
        ignored_failures = ['Unable to connect', 'timed out']
        for message in ignored_failures:
            if message in failure_reason:
                device_monitoring.save()
                return
        initial_status = device_monitoring.status
        status = 'ok' if is_working else 'problem'
        # do not send notifications if recovery made after firmware upgrade
        if status == initial_status == 'ok':
            device_monitoring.save()
            return
        if not is_working:
            if initial_status == 'ok':
                transaction_on_commit(lambda: trigger_device_checks.delay(pk=device.pk))
        else:
            # if checks exist trigger them else, set status as 'ok'
            if Check.objects.filter(object_id=instance.device.pk).exists():
                transaction_on_commit(lambda: trigger_device_checks.delay(pk=device.pk))
            else:
                device_monitoring.update_status(status)

    @classmethod
    def connect_config_status_changed(cls):
        Config = load_model('config', 'Config')

        if check_settings.AUTO_CONFIG_CHECK:
            config_status_changed.connect(
                cls.config_status_changed_receiver,
                sender=Config,
                dispatch_uid='monitoring.config_status_changed_receiver',
            )

    @classmethod
    def connect_wifi_client_signals(cls):
        if not app_settings.WIFI_SESSIONS_ENABLED:
            return
        WifiClient = load_model('device_monitoring', 'WifiClient')
        post_save.connect(
            WifiClient.invalidate_cache,
            sender=WifiClient,
            dispatch_uid='post_save_invalidate_wificlient_cache',
        )
        post_delete.connect(
            WifiClient.invalidate_cache,
            sender=WifiClient,
            dispatch_uid='post_delete_invalidate_wificlient_cache',
        )

    @classmethod
    def connect_offline_device_close_wifisession(cls):
        if not app_settings.WIFI_SESSIONS_ENABLED:
            return

        Metric = load_model('monitoring', 'Metric')
        WifiSession = load_model('device_monitoring', 'WifiSession')
        threshold_crossed.connect(
            WifiSession.offline_device_close_session,
            sender=Metric,
            dispatch_uid='offline_device_close_session',
        )

    @classmethod
    def config_status_changed_receiver(cls, sender, instance, **kwargs):
        from ..check.tasks import perform_check

        DeviceData = load_model('device_monitoring', 'DeviceData')
        device = DeviceData.objects.get(config=instance)
        check = device.checks.filter(check_type__contains='ConfigApplied').first()
        if check:
            transaction_on_commit(lambda: perform_check.delay(check.pk))

    def set_update_config_model(self):
        if not getattr(settings, 'OPENWISP_UPDATE_CONFIG_MODEL', None):
            setattr(
                connection_settings,
                'UPDATE_CONFIG_MODEL',
                'device_monitoring.DeviceData',
            )

    def register_dashboard_items(self):
        WifiSession = load_model('device_monitoring', 'WifiSession')
        Chart = load_model('monitoring', 'Chart')
        register_dashboard_chart(
            position=0,
            config={
                'name': _('Monitoring Status'),
                'query_params': {
                    'app_label': 'config',
                    'model': 'device',
                    'group_by': 'monitoring__status',
                },
                'colors': {
                    'ok': '#267126',
                    'problem': '#ffb442',
                    'critical': '#a72d1d',
                    'unknown': '#353c44',
                },
                'labels': {
                    'ok': app_settings.HEALTH_STATUS_LABELS['ok'],
                    'problem': app_settings.HEALTH_STATUS_LABELS['problem'],
                    'critical': app_settings.HEALTH_STATUS_LABELS['critical'],
                    'unknown': app_settings.HEALTH_STATUS_LABELS['unknown'],
                },
            },
        )

        if app_settings.DASHBOARD_MAP:
            loc_geojson_url = reverse_lazy(
                "monitoring:api_location_geojson", urlconf=MONITORING_API_URLCONF
            )
            device_list_url = reverse_lazy(
                "monitoring:api_location_device_list",
                urlconf=MONITORING_API_URLCONF,
                args=["000"],
            )
            if MONITORING_API_BASEURL:
                device_list_url = urljoin(MONITORING_API_BASEURL, str(device_list_url))
                loc_geojson_url = urljoin(MONITORING_API_BASEURL, str(loc_geojson_url))

            register_dashboard_template(
                position=0,
                config={
                    'template': 'admin/dashboard/device_map.html',
                    'css': (
                        'monitoring/css/device-map.css',
                        'leaflet/leaflet.css',
                        'monitoring/css/leaflet.fullscreen.css',
                        'monitoring/css/netjsongraph.css',
                    ),
                    'js': (
                        'monitoring/js/lib/netjsongraph.min.js',
                        'monitoring/js/lib/leaflet.fullscreen.min.js',
                        'monitoring/js/device-map.js',
                    ),
                },
                extra_config={
                    'monitoring_device_list_url': device_list_url,
                    'monitoring_location_geojson_url': loc_geojson_url,
                },
            )

        general_wifi_client_quick_links = {}
        if app_settings.WIFI_SESSIONS_ENABLED:
            register_dashboard_chart(
                position=13,
                config={
                    'name': _('Currently Active WiFi Sessions'),
                    'query_params': {
                        'app_label': WifiSession._meta.app_label,
                        'model': WifiSession._meta.model_name,
                        'filter': {'stop_time__isnull': True},
                        'aggregate': {
                            'active__count': Count('id'),
                        },
                        'organization_field': 'device__organization_id',
                    },
                    'filters': {
                        'key': 'stop_time__isnull',
                        'active__count': 'true',
                    },
                    'colors': {
                        'active__count': '#267126',
                    },
                    'labels': {
                        'active__count': _('Currently Active WiFi Sessions'),
                    },
                    'quick_link': {
                        'url': reverse_lazy(
                            'admin:{app_label}_{model_name}_changelist'.format(
                                app_label=WifiSession._meta.app_label,
                                model_name=WifiSession._meta.model_name,
                            )
                        ),
                        'label': _('Open WiFi session list'),
                        'title': _('View full history of WiFi Sessions'),
                        'custom_css_classes': ['negative-top-20'],
                    },
                },
            )

            general_wifi_client_quick_links = {
                'General WiFi Clients': {
                    'url': reverse_lazy(
                        'admin:{app_label}_{model_name}_changelist'.format(
                            app_label=WifiSession._meta.app_label,
                            model_name=WifiSession._meta.model_name,
                        )
                    ),
                    'label': _('Open WiFi session list'),
                    'title': _('View full history of WiFi Sessions'),
                }
            }

        register_dashboard_template(
            position=55,
            config={
                'template': 'monitoring/paritals/chart.html',
                'css': (
                    'monitoring/css/daterangepicker.css',
                    'monitoring/css/percircle.min.css',
                    'monitoring/css/chart.css',
                    'monitoring/css/dashboard-chart.css',
                    'admin/css/vendor/select2/select2.min.css',
                    'admin/css/autocomplete.css',
                ),
                'js': (
                    'admin/js/vendor/select2/select2.full.min.js',
                    'monitoring/js/lib/moment.min.js',
                    'monitoring/js/lib/daterangepicker.min.js',
                    'monitoring/js/lib/percircle.min.js',
                    'monitoring/js/chart.js',
                    'monitoring/js/chart-utils.js',
                    'monitoring/js/dashboard-chart.js',
                ),
            },
            extra_config={
                'api_url': reverse_lazy('monitoring_general:api_dashboard_timeseries'),
                'default_time': Chart.DEFAULT_TIME,
                'chart_quick_links': general_wifi_client_quick_links,
            },
            after_charts=True,
        )

    def register_menu_groups(self):
        if app_settings.WIFI_SESSIONS_ENABLED:
            register_menu_subitem(
                group_position=80,
                item_position=0,
                config={
                    'label': _('WiFi Sessions'),
                    'model': get_model_name('device_monitoring', 'WifiSession'),
                    'name': 'changelist',
                    'icon': 'ow-monitoring-wifi',
                },
            )

    def add_connection_ignore_notification_reasons(self):
        from openwisp_controller.connection.apps import ConnectionConfig

        ConnectionConfig._ignore_connection_notification_reasons.extend(
            ['timed out', 'Unable to connect']
        )
