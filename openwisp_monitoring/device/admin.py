import uuid

from django.contrib import admin
from django.contrib.contenttypes.admin import GenericStackedInline
from django.contrib.contenttypes.forms import BaseGenericInlineFormSet
from django.contrib.contenttypes.models import ContentType
from django.forms import ModelForm
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from nested_admin.nested import (
    NestedGenericStackedInline,
    NestedModelAdmin,
    NestedStackedInline,
)
from swapper import load_model

from openwisp_controller.config.admin import DeviceAdmin as BaseDeviceAdmin

from ..monitoring.admin import MetricAdmin
from . import settings as app_settings

DeviceData = load_model('device_monitoring', 'DeviceData')
DeviceMonitoring = load_model('device_monitoring', 'DeviceMonitoring')
AlertSettings = load_model('monitoring', 'AlertSettings')
Chart = load_model('monitoring', 'Chart')
Device = load_model('config', 'Device')
Metric = load_model('monitoring', 'Metric')
Notification = load_model('openwisp_notifications', 'Notification')
Check = load_model('check', 'Check')


class CheckInlineFormSet(BaseGenericInlineFormSet):
    def full_clean(self):
        for form in self.forms:
            obj = form.instance
            if not obj.content_type or not obj.object_id:
                setattr(
                    form.instance,
                    self.ct_field.get_attname(),
                    ContentType.objects.get_for_model(self.instance).pk,
                )
                setattr(form.instance, self.ct_fk_field.get_attname(), self.instance.pk)
        super().full_clean()


class CheckInline(GenericStackedInline):
    model = Check
    extra = 0
    formset = CheckInlineFormSet
    fields = ['name', 'check', 'is_active']
    readonly_fields = ['name', 'check']

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


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


class AlertSettingsInline(NestedStackedInline):
    model = AlertSettings
    extra = 0
    max_num = 0
    exclude = ['created', 'modified']
    form = AlertSettingsForm

    def get_queryset(self, request):
        return super().get_queryset(request).order_by('created')

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class MetricInline(NestedGenericStackedInline):
    model = Metric
    extra = 0
    inlines = [AlertSettingsInline]
    readonly_fields = ['name', 'is_healthy']
    fields = ['name', 'is_healthy']
    # Explicitly changed name from Metrics to Alert Settings
    verbose_name = _('Alert Settings')
    verbose_name_plural = verbose_name

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).filter(alertsettings__isnull=False)


class DeviceAdmin(BaseDeviceAdmin, NestedModelAdmin):
    change_form_template = 'admin/config/device/change_form.html'

    def get_extra_context(self, pk=None):
        ctx = super().get_extra_context(pk)
        if pk:
            device_data = DeviceData(pk=uuid.UUID(pk))
            api_url = reverse('monitoring:api_device_metric', args=[pk])
            ctx.update(
                {
                    'device_data': device_data.data_user_friendly,
                    'api_url': api_url,
                    'default_time': Chart.DEFAULT_TIME,
                    'MAC_VENDOR_DETECTION': app_settings.MAC_VENDOR_DETECTION,
                }
            )
        return ctx

    def metric_health(self, obj):
        metric_rows = []
        for metric in DeviceData(pk=obj.pk).metrics.all():
            # Skip metrics which don't affect device health
            if metric.is_healthy is None:
                continue
            health = 'yes' if metric.is_healthy else 'no'
            metric_rows.append(
                f'<li><img src="/static/admin/img/icon-{health}.svg" '
                f'alt="health"> {metric.name}</li>'
            )
        return format_html(
            mark_safe(f'<ul class="metric_health">{"".join(metric_rows)}</ul>'),
        )

    def health_status(self, obj):
        return format_html(
            mark_safe('<span class="health-{0}">{1}</span>'),
            obj.monitoring.status,
            obj.monitoring.get_status_display(),
        )

    health_status.short_description = _('health status')

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
        if not obj or obj.monitoring.status != 'problem':
            return self.fields
        fields = list(self.fields)
        fields.insert(fields.index('last_ip'), 'metric_health')
        return fields

    def get_readonly_fields(self, request, obj=None):
        if not obj or obj.monitoring.status != 'problem':
            return self.readonly_fields
        readonly_fields = list(self.readonly_fields)
        readonly_fields.append('metric_health')
        return readonly_fields


def device_admin_get_inlines(self, request, obj):
    # copy the list to avoid modifying the original data structure
    inlines = list(super(DeviceAdmin, self).get_inlines(request, obj))
    if not obj or obj._state.adding:
        inlines.remove(MetricInline)
        return inlines
    return inlines


DeviceAdmin.inlines += [CheckInline, MetricInline]
# This attribute needs to be set for nested inline
for inline in DeviceAdmin.inlines:
    if not hasattr(inline, 'sortable_options'):
        inline.sortable_options = {'disabled': True}

DeviceAdmin.get_inlines = device_admin_get_inlines

DeviceAdmin.Media.js += MetricAdmin.Media.js + (
    'monitoring/js/percircle.js',
    'monitoring/js/alert-settings.js',
)
DeviceAdmin.Media.css['all'] += (
    'monitoring/css/percircle.css',
) + MetricAdmin.Media.css['all']

DeviceAdmin.list_display.insert(
    DeviceAdmin.list_display.index('config_status'), 'health_status'
)
DeviceAdmin.list_select_related += ('monitoring',)
DeviceAdmin.list_filter.insert(
    0, 'monitoring__status',
)
DeviceAdmin.fields.insert(DeviceAdmin.fields.index('last_ip'), 'health_status')
DeviceAdmin.readonly_fields.append('health_status')

admin.site.unregister(Device)
admin.site.register(Device, DeviceAdmin)
