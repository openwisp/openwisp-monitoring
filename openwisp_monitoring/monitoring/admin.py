from django.contrib import admin
from django.utils.translation import ugettext_lazy as _
from swapper import load_model

from openwisp_utils.admin import TimeReadonlyAdminMixin

Graph = load_model('monitoring', 'Graph')
Metric = load_model('monitoring', 'Metric')
AlertSettings = load_model('monitoring', 'AlertSettings')


class AlertSettingsInline(TimeReadonlyAdminMixin, admin.StackedInline):
    model = AlertSettings
    extra = 0


class GraphInline(admin.StackedInline):
    model = Graph
    extra = 0
    template = 'admin/graph_inline.html'
    exclude = ['created', 'modified']


@admin.register(Metric)
class MetricAdmin(TimeReadonlyAdminMixin, admin.ModelAdmin):
    list_display = ['__str__', 'created', 'modified']
    readonly_fields = ['is_healthy']
    search_fields = ['name']
    save_on_top = True
    inlines = [GraphInline, AlertSettingsInline]
    fieldsets = [
        (None, {'fields': ('name', 'description', 'content_type', 'object_id',)}),
        (
            _('Advanced options'),
            {'classes': ('collapse',), 'fields': ('key', 'field_name')},
        ),
    ]

    class Media:
        css = {'all': ('monitoring/css/monitoring.css',)}
        js = ('monitoring/js/plotly-cartesian.min.js', 'monitoring/js/graph.js')


@admin.register(AlertSettings)
class AlertSettingsAdmin(TimeReadonlyAdminMixin, admin.ModelAdmin):
    list_display = ['metric', 'created', 'modified']
    search_fields = ['name']
    save_on_top = True
