from django.contrib import admin
from django.forms import ModelForm
from django.templatetags.static import static
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from reversion.admin import VersionAdmin
from swapper import load_model

from openwisp_utils.admin import ReadOnlyAdmin, TimeReadonlyAdminMixin

Chart = load_model('monitoring', 'Chart')
Metric = load_model('monitoring', 'Metric')
AlertSettings = load_model('monitoring', 'AlertSettings')
WifiSession = load_model('monitoring', 'WifiSession')
Device = load_model('config', 'Device')
Organization = load_model('openwisp_users', 'Organization')


class AlertSettingsForm(ModelForm):
    def __init__(self, *args, **kwargs):
        instance = kwargs.get('instance')
        if instance:
            kwargs['initial'] = {
                'custom_tolerance': instance.tolerance,
                'custom_threshold': instance.threshold,
                'custom_operator': instance.operator,
            }
        super().__init__(*args, **kwargs)


class AlertSettingsInline(TimeReadonlyAdminMixin, admin.StackedInline):
    model = AlertSettings
    form = AlertSettingsForm
    extra = 0


class ChartInline(admin.StackedInline):
    model = Chart
    extra = 0
    template = 'admin/chart_inline.html'
    exclude = ['created', 'modified']


@admin.register(Metric)
class MetricAdmin(TimeReadonlyAdminMixin, VersionAdmin):
    list_display = ['__str__', 'created', 'modified']
    readonly_fields = ['is_healthy']
    search_fields = ['name']
    save_on_top = True
    inlines = [ChartInline, AlertSettingsInline]
    fieldsets = [
        (None, {'fields': ('name', 'content_type', 'object_id', 'configuration')}),
        (
            _('Advanced options'),
            {'classes': ('collapse',), 'fields': ('key', 'field_name')},
        ),
    ]

    class Media:
        css = {'all': ('monitoring/css/monitoring.css',)}
        js = ('monitoring/js/plotly-cartesian.min.js', 'monitoring/js/chart.js')

    def reversion_register(self, model, **options):
        if model == Metric:
            options['follow'] = (
                *(options['follow']),
                'content_object',
                'chart_set',
            )
        if model == AlertSettings:
            options['follow'] = (
                *(options['follow']),
                'metric',
            )
        if model == Chart:
            options['follow'] = (*options['follow'], 'metric')
        return super().reversion_register(model, **options)


class WifiSessionAdmin(ReadOnlyAdmin):
    model = WifiSession
    list_display = [
        'mac_address',
        'vendor',
        'related_organization',
        'related_device',
        'ssid',
        'ht',
        'vht',
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
        'ht',
        'vht',
        'wmm',
        'wds',
        'wps',
        'start_time',
        'get_stop_time',
        'modified',
    ]

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        fields += [
            'related_organization',
            'mac_address',
            'vendor',
            'ht',
            'vht',
            'wmm',
            'wds',
            'wps',
            'get_stop_time',
            'modified',
            'related_device',
        ]
        return fields

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('wifi_client', 'device')

    def _get_boolean_html(self, value):
        icon = static('/admin/img/icon-{}.svg'.format('yes' if value is True else 'no'))
        return mark_safe(f'<img src="{icon}">')

    @admin.display(description='HT')
    def ht(self, obj):
        return self._get_boolean_html(obj.wifi_client.ht)

    @admin.display(description='VHT')
    def vht(self, obj):
        return self._get_boolean_html(obj.wifi_client.vht)

    @admin.display(description='WMM')
    def wmm(self, obj):
        return self._get_boolean_html(obj.wifi_client.wmm)

    @admin.display(description='WDS')
    def wds(self, obj):
        return self._get_boolean_html(obj.wifi_client.wds)

    @admin.display(description='WPS')
    def wps(self, obj):
        return self._get_boolean_html(obj.wifi_client.wps)

    @admin.display(description=_('stop time'))
    def get_stop_time(self, obj):
        if obj.stop_time is None:
            return mark_safe('<strong style="color:green;">online</strong>')
        return obj.stop_time

    @admin.display(description=_('device'))
    def related_device(self, obj):
        app_label = Device._meta.app_label
        url = reverse(f'admin:{app_label}_device_change', args=[obj.device_id])
        return mark_safe(f'<a href="{url}">{obj.device}</a>')

    @admin.display(description=_('organization'))
    def related_organization(self, obj):
        app_label = Organization._meta.app_label
        url = reverse(
            f'admin:{app_label}_organization_change', args=[obj.organization.id]
        )
        return mark_safe(f'<a href="{url}">{obj.organization}</a>')


admin.site.register(WifiSession, WifiSessionAdmin)
