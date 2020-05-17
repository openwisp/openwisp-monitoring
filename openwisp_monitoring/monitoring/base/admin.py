from django.contrib import admin
from django.utils.translation import ugettext_lazy as _
from swapper import load_model

from openwisp_utils.admin import TimeReadonlyAdminMixin


class ThresholdInline(TimeReadonlyAdminMixin, admin.StackedInline):
    model = load_model('monitoring', 'Threshold')
    extra = 0


class GraphInline(admin.StackedInline):
    model = load_model('monitoring', 'Graph')
    extra = 0
    template = 'admin/graph_inline.html'
    exclude = ['created', 'modified']


class AbstractMetricAdmin(TimeReadonlyAdminMixin, admin.ModelAdmin):
    list_display = ('__str__', 'created', 'modified')
    readonly_fields = ['is_healthy']
    search_fields = ['name']
    save_on_top = True
    inlines = [GraphInline, ThresholdInline]
    fieldsets = (
        (None, {'fields': ('name', 'description', 'content_type', 'object_id',)}),
        (
            _('Advanced options'),
            {'classes': ('collapse',), 'fields': ('key', 'field_name')},
        ),
    )

    class Media:
        css = {'all': ('monitoring/css/monitoring.css',)}
        js = ('monitoring/js/plotly-cartesian.min.js', 'monitoring/js/graph.js')


class AbstracThresholdAdmin(TimeReadonlyAdminMixin, admin.ModelAdmin):
    list_display = ('metric', 'created', 'modified')
    search_fields = ['name']
    save_on_top = True
