from django.contrib import admin
from django.utils.translation import ugettext_lazy as _
from notifications.models import Notification

from openwisp_controller.admin import AlwaysHasChangedMixin
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


Notification.__str__ = lambda self: self.timesince()
admin.site.unregister(Notification)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    raw_id_fields = ('recipient', )
    list_display = ('description', 'unread', 'level', 'timesince')
    list_filter = ('level', 'unread', )
    actions = None
    fieldsets = (
        (None, {
            'fields': ('timestamp', 'level', 'description', 'emailed',)
        }),
        (_('Advanced options'), {
            'classes': ('collapse',),
            'fields': ('actor_content_type', 'actor_object_id',
                       'action_object_content_type', 'action_object_object_id',
                       'target_content_type', 'target_object_id',
                       'data'),
        }),
    )

    class Media:
        js = ('notifications/js/admin.js',)
        css = {'all': ('notifications/css/admin.css',)}

    def get_queryset(self, request):
        return self.model.objects.filter(recipient=request.user)

    def get_readonly_fields(self, request, obj=None):
        return self.fields or [f.name for f in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    # Allow viewing objects but not actually changing them.
    def has_change_permission(self, request, obj=None):
        return (request.method in ['GET', 'HEAD'] and
                super(NotificationAdmin, self).has_change_permission(request, obj))

    def has_delete_permission(self, request, obj=None):
        return False

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        if obj and obj.unread:
            obj.unread = False
            obj.save()
        return super(NotificationAdmin, self).render_change_form(request, context, add=False,
                                                                 change=False, form_url='', obj=None)
