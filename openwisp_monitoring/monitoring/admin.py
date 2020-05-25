from django.contrib import admin, messages
from django.contrib.admin.utils import model_ngettext
from django.template.response import TemplateResponse
from django.utils.translation import ugettext_lazy as _

from openwisp_utils.admin import TimeReadonlyAdminMixin

from .models import Graph, Metric, Threshold


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
    actions = ['disable_notifications', 'enable_notifications']

    def require_confirmation(func):
        """
        Decorator to lead to a confirmation page.
        This has been used rather than simply adding the same lines in action functions
        in order to avoid repetition of the same lines in the two added actions and more actions
        in case they are added in future.
        """

        def wrapper(modeladmin, request, queryset):
            opts = modeladmin.model._meta
            if request.POST.get('confirmation') is None:
                request.current_app = modeladmin.admin_site.name
                context = {
                    'action': request.POST['action'],
                    'queryset': queryset,
                    'opts': opts,
                }
                return TemplateResponse(request, 'admin/confirmation.html', context)
            return func(modeladmin, request, queryset)

        wrapper.__name__ = func.__name__
        return wrapper

    @require_confirmation
    def disable_notifications(self, request, queryset):
        queryset.update(notifications_enabled=False)
        count = queryset.count()
        if count:
            self.message_user(
                request,
                _(
                    f'Successfully disabled notifications for {count} {model_ngettext(self.opts, count)}.'
                ),
                messages.SUCCESS,
            )

    disable_notifications.short_description = _(
        'Disable notifications for selected metrics'
    )

    @require_confirmation
    def enable_notifications(self, request, queryset):
        queryset.update(notifications_enabled=True)
        count = queryset.count()
        if count:
            self.message_user(
                request,
                _(
                    f'Successfully enabled notifications for {count} {model_ngettext(self.opts, count)}.'
                ),
                messages.SUCCESS,
            )

    enable_notifications.short_description = _(
        'Enable notifications for selected metrics'
    )

    class Media:
        css = {'all': ('monitoring/css/monitoring.css',)}
        js = ('monitoring/js/plotly-cartesian.min.js', 'monitoring/js/graph.js')


@admin.register(Threshold)
class ThresholdAdmin(TimeReadonlyAdminMixin, admin.ModelAdmin):
    list_display = ('metric', 'created', 'modified')
    search_fields = ['name']
    save_on_top = True
