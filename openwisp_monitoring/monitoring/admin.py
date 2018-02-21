from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import ugettext_lazy as _

from openwisp_controller.admin import AlwaysHasChangedMixin
from openwisp_controller.config.admin import DeviceAdmin as BaseDeviceAdmin
from openwisp_controller.config.models import Device
from openwisp_users.admin import UserAdmin
from openwisp_utils.admin import TimeReadonlyAdminMixin

from .models import Graph, Metric, NotificationUser, Threshold


class ThresholdInline(TimeReadonlyAdminMixin, admin.StackedInline):
    model = Threshold
    extra = 0


class GraphInline(admin.StackedInline):
    model = Graph
    extra = 0
    template = 'admin/graph_inline.html'
    exclude = ['created', 'modified']


@admin.register(Metric)
class MetricAdmin(TimeReadonlyAdminMixin, admin.ModelAdmin):
    list_display = ('__str__', 'created', 'modified')
    readonly_fields = ['health']
    search_fields = ['name']
    save_on_top = True
    inlines = [GraphInline, ThresholdInline]
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'content_type', 'object_id',)
        }),
        (_('Advanced options'), {
            'classes': ('collapse',),
            'fields': ('key', 'field_name'),
        }),
    )

    class Media:
        js = ('monitoring/js/plotly.min.js',
              'monitoring/js/graph.js')


@admin.register(Threshold)
class ThresholdAdmin(TimeReadonlyAdminMixin, admin.ModelAdmin):
    list_display = ('metric', 'created', 'modified')
    search_fields = ['name']
    save_on_top = True


class NotificationUserInline(AlwaysHasChangedMixin, admin.StackedInline):
    model = NotificationUser
    fields = ('receive', 'email')


UserAdmin.inlines.insert(len(UserAdmin.inlines) - 1,
                         NotificationUserInline)


class DeviceAdmin(BaseDeviceAdmin):
    def get_extra_context(self, pk=None):
        ctx = super(DeviceAdmin, self).get_extra_context(pk)
        if pk:
            ct = ContentType.objects.get(model=self.model.__name__.lower(),
                                         app_label=self.model._meta.app_label)
            graphs = Graph.objects.filter(metric__object_id=pk,
                                          metric__content_type=ct)
            ctx.update({'graphs': graphs})
        return ctx


DeviceAdmin.Media.js += MetricAdmin.Media.js


admin.site.unregister(Device)
admin.site.register(Device, DeviceAdmin)
