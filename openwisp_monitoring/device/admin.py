import uuid
from urllib.parse import urljoin

from django.contrib import admin
from django.contrib.contenttypes.admin import GenericStackedInline
from django.contrib.contenttypes.forms import BaseGenericInlineFormSet
from django.contrib.contenttypes.models import ContentType
from django.forms import ModelForm
from django.templatetags.static import static
from django.urls import resolve, reverse
from django.utils import timezone
from django.utils.formats import localize
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from import_export.admin import ImportExportMixin
from nested_admin.nested import (
    NestedGenericStackedInline,
    NestedModelAdmin,
    NestedStackedInline,
)
from swapper import load_model

from openwisp_controller.config.admin import DeviceAdmin as BaseDeviceAdmin
from openwisp_users.multitenancy import MultitenantAdminMixin
from openwisp_utils.admin import ReadOnlyAdmin

from ..monitoring.admin import MetricAdmin
from ..settings import MONITORING_API_BASEURL, MONITORING_API_URLCONF
from . import settings as app_settings
from .exportable import DeviceMonitoringResource
from .filters import DeviceFilter, DeviceGroupFilter, DeviceOrganizationFilter

DeviceData = load_model('device_monitoring', 'DeviceData')
WifiSession = load_model('device_monitoring', 'WifiSession')
DeviceMonitoring = load_model('device_monitoring', 'DeviceMonitoring')
AlertSettings = load_model('monitoring', 'AlertSettings')
Chart = load_model('monitoring', 'Chart')
Device = load_model('config', 'Device')
Metric = load_model('monitoring', 'Metric')
Notification = load_model('openwisp_notifications', 'Notification')
Check = load_model('check', 'Check')
Organization = load_model('openwisp_users', 'Organization')


class CheckInlineFormSet(BaseGenericInlineFormSet):
    def full_clean(self):
        for form in self.forms:
            obj = form.instance
            if not obj.content_type or not obj.object_id:
                setattr(
                    obj,
                    self.ct_field.get_attname(),
                    ContentType.objects.get_for_model(self.instance).pk,
                )
                setattr(obj, self.ct_fk_field.get_attname(), self.instance.pk)
        super().full_clean()


class InlinePermissionMixin:
    def has_add_permission(self, request, obj=None):
        # User will be able to add objects from inline even
        # if it only has permission to add a model object
        return super().has_add_permission(request, obj) or request.user.has_perm(
            f'{self.model._meta.app_label}.add_{self.inline_permission_suffix}'
        )

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) or request.user.has_perm(
            f'{self.model._meta.app_label}.change_{self.inline_permission_suffix}'
        )

    def has_view_permission(self, request, obj=None):
        return super().has_view_permission(request, obj) or request.user.has_perm(
            f'{self.model._meta.app_label}.view_{self.inline_permission_suffix}'
        )

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) or request.user.has_perm(
            f'{self.model._meta.app_label}.delete_{self.inline_permission_suffix}'
        )


class CheckInline(InlinePermissionMixin, GenericStackedInline):
    model = Check
    extra = 0
    formset = CheckInlineFormSet
    fields = [
        'is_active',
        'check_type',
    ]
    inline_permission_suffix = 'check_inline'

    def get_fields(self, request, obj=None):
        if not self.has_change_permission(request, obj) or not self.has_view_permission(
            request, obj
        ):
            return ['check_type', 'is_active']
        return super().get_fields(request, obj)

    def get_readonly_fields(self, request, obj=None):
        if not self.has_change_permission(request, obj) or not self.has_view_permission(
            request, obj
        ):
            return ['check_type']
        return super().get_readonly_fields(request, obj)


class AlertSettingsForm(ModelForm):
    def __init__(self, *args, **kwargs):
        instance = kwargs.get('instance')
        if instance:
            kwargs['initial'] = {
                'custom_tolerance': instance.tolerance,
                'custom_operator': instance.operator,
                'custom_threshold': instance.threshold,
            }
        super().__init__(*args, **kwargs)

    def _post_clean(self):
        self.instance._delete_instance = False
        if all(
            self.cleaned_data[field] is None
            for field in [
                'custom_operator',
                'custom_threshold',
                'custom_tolerance',
            ]
        ):
            # "_delete_instance" flag signifies that
            # the fields have been set to None by the
            # user. Hence, the object should be deleted.
            self.instance._delete_instance = True
        super()._post_clean()

    def save(self, commit=True):
        if self.instance._delete_instance:
            self.instance.delete()
            return self.instance
        return super().save(commit)


class AlertSettingsInline(InlinePermissionMixin, NestedStackedInline):
    model = AlertSettings
    extra = 1
    max_num = 1
    exclude = ['created', 'modified']
    form = AlertSettingsForm
    inline_permission_suffix = 'alertsettings_inline'

    def get_queryset(self, request):
        return super().get_queryset(request).order_by('created')


class MetricInline(InlinePermissionMixin, NestedGenericStackedInline):
    model = Metric
    extra = 0
    inlines = [AlertSettingsInline]
    fieldsets = [
        (
            None,
            {
                'fields': (
                    'name',
                    'is_healthy',
                )
            },
        ),
        (
            _('Advanced options'),
            {'classes': ('collapse',), 'fields': ('field_name',)},
        ),
    ]

    readonly_fields = ['name', 'is_healthy']
    # Explicitly changed name from Metrics to Alert Settings
    verbose_name = _('Alert Settings')
    verbose_name_plural = verbose_name
    inline_permission_suffix = 'alertsettings_inline'
    # Ordering queryset by metric name
    ordering = ('name',)

    def get_fieldsets(self, request, obj=None):
        if not self.has_change_permission(request, obj) or not self.has_view_permission(
            request, obj
        ):
            return [
                (None, {'fields': ('is_healthy',)}),
            ]
        return super().get_fieldsets(request, obj)

    def get_queryset(self, request):
        # Only show 'Metrics' that have 'AlertSettings' objects
        return super().get_queryset(request).filter(alertsettings__isnull=False)

    def has_add_permission(self, request, obj=None):
        # We need to restrict the users from adding the 'metrics' since
        # they're created by the system automatically with default 'alertsettings'
        return False

    def has_delete_permission(self, request, obj=None):
        # We need to restrict the users from deleting the 'metrics' since
        # they're created by the system automatically with default 'alertsettings'
        return False


class DeviceAdmin(BaseDeviceAdmin, NestedModelAdmin):
    change_form_template = 'admin/config/device/change_form.html'
    list_filter = ['monitoring__status'] + BaseDeviceAdmin.list_filter
    list_select_related = ['monitoring'] + list(BaseDeviceAdmin.list_select_related)
    list_display = list(BaseDeviceAdmin.list_display)
    list_display.insert(list_display.index('config_status'), 'health_status')
    readonly_fields = ['health_status'] + BaseDeviceAdmin.readonly_fields

    class Media:
        js = (
            tuple(BaseDeviceAdmin.Media.js)
            + (
                'monitoring/js/lib/percircle.min.js',
                'monitoring/js/alert-settings.js',
            )
            + MetricAdmin.Media.js
            + ('monitoring/js/chart-utils.js',)
            + ('monitoring/js/lib/moment.min.js',)
            + ('monitoring/js/lib/daterangepicker.min.js',)
        )
        css = {
            'all': (
                'monitoring/css/percircle.min.css',
                'monitoring/css/daterangepicker.css',
            )
            + MetricAdmin.Media.css['all']
        }

    def get_extra_context(self, pk=None):
        ctx = super().get_extra_context(pk)
        if pk:
            device_data = DeviceData(pk=uuid.UUID(pk))
            api_url = reverse(
                'monitoring:api_device_metric',
                urlconf=MONITORING_API_URLCONF,
                args=[pk],
            )
            if MONITORING_API_BASEURL:
                api_url = urljoin(MONITORING_API_BASEURL, api_url)
            ctx.update(
                {
                    'device_data': device_data.data_user_friendly,
                    'api_url': api_url,
                    'default_time': Chart.DEFAULT_TIME,
                    'MAC_VENDOR_DETECTION': app_settings.MAC_VENDOR_DETECTION,
                }
            )
        return ctx

    def health_checks(self, obj):
        metric_rows = []
        for metric in DeviceData(pk=obj.pk).metrics.filter(alertsettings__isnull=False):
            health = 'yes' if metric.is_healthy else 'no'
            icon_url = static(f'admin/img/icon-{health}.svg')
            metric_rows.append(
                f'<li><img src="{icon_url}" ' f'alt="health"> {metric.name}</li>'
            )
        return format_html(
            mark_safe(f'<ul class="health_checks">{"".join(metric_rows)}</ul>')
        )

    health_checks.short_description = _('health checks')

    def health_status(self, obj):
        return format_html(
            mark_safe('<span class="health-{0}">{1}</span>'),
            obj.monitoring.status,
            obj.monitoring.get_status_display(),
        )

    health_status.short_description = _('health status')

    def get_object(self, request, object_id, from_field=None):
        obj = super().get_object(request, object_id, from_field=from_field)
        if obj and obj.wifisession_set.exists():
            # We need to provide default formset values
            # to avoid management formset errors when wifi sessions
            # are created while editing the DeviceAdmin change page
            wifisession_formset_data = {
                'wifisession_set-TOTAL_FORMS': '1',
                'wifisession_set-INITIAL_FORMS': '1',
            }
            request.POST = request.POST.copy()
            request.POST.update(wifisession_formset_data)
        return obj

    def get_form(self, request, obj=None, **kwargs):
        """
        Adds the help_text of DeviceMonitoring.status field
        """
        health_status = DeviceMonitoring._meta.get_field('status').help_text
        kwargs.update(
            {'help_texts': {'health_status': health_status.replace('\n', '<br>')}}
        )
        return super().get_form(request, obj, **kwargs)

    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj))
        if obj and not obj._state.adding:
            fields.insert(fields.index('last_ip'), 'health_status')
        if not obj or obj.monitoring.status in ['ok', 'unknown']:
            return fields
        fields.insert(fields.index('health_status') + 1, 'health_checks')
        return fields

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = super().get_readonly_fields(request, obj)
        if not obj or obj.monitoring.status in ['ok', 'unknown']:
            return readonly_fields
        readonly_fields = list(readonly_fields)
        readonly_fields.append('health_checks')
        return readonly_fields

    def get_inlines(self, request, obj=None):
        inlines = super().get_inlines(request, obj)
        inlines = list(inlines + [CheckInline, MetricInline])
        # This attribute needs to be set for nested inline
        for inline in inlines:
            if not hasattr(inline, 'sortable_options'):
                inline.sortable_options = {'disabled': True}
        if not obj or obj._state.adding or obj.organization.is_active is False:
            inlines.remove(CheckInline)
            inlines.remove(MetricInline)
        return inlines


class DeviceAdminExportable(ImportExportMixin, DeviceAdmin):
    resource_class = DeviceMonitoringResource
    # Added to support both reversion and import-export
    change_list_template = 'admin/config/change_list_device.html'


class WifiSessionAdminHelperMixin:
    def _get_boolean_html(self, value):
        icon_type = 'unknown'
        if value is True:
            icon_type = 'yes'
        elif value is False:
            icon_type = 'no'
        icon = static(f'admin/img/icon-{icon_type}.svg')
        return mark_safe(f'<img src="{icon}">')

    def he(self, obj):
        return self._get_boolean_html(obj.wifi_client.he)

    he.short_description = 'WiFi 6 (802.11ax)'

    def vht(self, obj):
        return self._get_boolean_html(obj.wifi_client.vht)

    vht.short_description = 'WiFi 5 (802.11ac)'

    def ht(self, obj):
        return self._get_boolean_html(obj.wifi_client.ht)

    ht.short_description = 'WiFi 4 (802.11n)'

    def wmm(self, obj):
        return self._get_boolean_html(obj.wifi_client.wmm)

    wmm.short_description = 'WMM'

    def wds(self, obj):
        return self._get_boolean_html(obj.wifi_client.wds)

    wds.short_description = 'WDS'

    def wps(self, obj):
        return self._get_boolean_html(obj.wifi_client.wps)

    wps.short_description = 'WPS'

    def get_stop_time(self, obj):
        if obj.stop_time is None:
            return mark_safe('<strong style="color:green;">online</strong>')
        return localize(timezone.localtime(obj.stop_time))

    get_stop_time.short_description = _('stop time')

    def related_device(self, obj):
        app_label = Device._meta.app_label
        url = reverse(f'admin:{app_label}_device_change', args=[obj.device_id])
        return mark_safe(f'<a href="{url}">{obj.device}</a>')

    related_device.short_description = _('device')

    def related_organization(self, obj):
        app_label = Organization._meta.app_label
        url = reverse(
            f'admin:{app_label}_organization_change', args=[obj.device.organization_id]
        )
        return mark_safe(f'<a href="{url}">{obj.device.organization}</a>')

    related_organization.short_description = _('organization')


class WiFiSessionInline(WifiSessionAdminHelperMixin, admin.TabularInline):
    model = WifiSession
    fk_name = 'device'
    fields = [
        'get_mac_address',
        'vendor',
        'ssid',
        'interface_name',
        'he',
        'vht',
        'ht',
        'start_time',
        'get_stop_time',
    ]
    readonly_fields = fields
    can_delete = False
    extra = 0
    template = 'admin/config/device/wifisession_tabular.html'

    class Media:
        css = {'all': ('monitoring/css/wifi-sessions.css',)}
        js = ['admin/js/jquery.init.js', 'monitoring/js/wifi-session-inline.js']

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request, select_related=True):
        qs = super().get_queryset(request).filter(stop_time__isnull=True)
        resolved = resolve(request.path_info)
        if 'object_id' in resolved.kwargs:
            qs = qs.filter(device_id=resolved.kwargs['object_id'])
        if select_related:
            qs = qs.select_related('wifi_client')
        return qs

    def _get_conditional_queryset(self, request, obj, select_related=False):
        return self.get_queryset(request, select_related=select_related).exists()

    def get_mac_address(self, obj):
        app_label = WifiSession._meta.app_label
        url = reverse(f'admin:{app_label}_wifisession_change', args=[obj.id])
        return mark_safe(f'<a href="{url}">{obj.mac_address}</a>')

    get_mac_address.short_description = _('MAC address')


class WifiSessionAdmin(
    WifiSessionAdminHelperMixin, MultitenantAdminMixin, ReadOnlyAdmin
):
    multitenant_parent = 'device'
    model = WifiSession
    list_display = [
        'mac_address',
        'vendor',
        'related_organization',
        'related_device',
        'ssid',
        'he',
        'vht',
        'ht',
        'start_time',
        'get_stop_time',
    ]
    fields = [
        'related_organization',
        'mac_address',
        'vendor',
        'related_device',
        'ssid',
        'interface_name',
        'he',
        'vht',
        'ht',
        'wmm',
        'wds',
        'wps',
        'start_time',
        'get_stop_time',
        'modified',
    ]
    search_fields = ['wifi_client__mac_address', 'device__name', 'device__mac_address']
    list_filter = [
        DeviceOrganizationFilter,
        DeviceFilter,
        DeviceGroupFilter,
        'start_time',
        'stop_time',
    ]

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        fields += [
            'related_organization',
            'mac_address',
            'vendor',
            'he',
            'vht',
            'ht',
            'wmm',
            'wds',
            'wps',
            'get_stop_time',
            'modified',
            'related_device',
        ]
        return fields

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                'wifi_client', 'device', 'device__organization', 'device__group'
            )
        )

    def has_delete_permission(self, request, obj=None):
        return super(admin.ModelAdmin, self).has_delete_permission(request, obj)


admin.site.unregister(Device)
admin.site.register(Device, DeviceAdminExportable)

if app_settings.WIFI_SESSIONS_ENABLED:
    admin.site.register(WifiSession, WifiSessionAdmin)
    DeviceAdmin.conditional_inlines.append(WiFiSessionInline)
