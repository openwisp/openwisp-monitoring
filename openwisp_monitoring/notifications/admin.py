from django.contrib import admin
from django.utils.translation import ugettext_lazy as _

from openwisp_users.admin import UserAdmin
from openwisp_utils.admin import AlwaysHasChangedMixin

from .models import Notification, NotificationUser


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    raw_id_fields = ('recipient', )
    list_display = ('description', 'read', 'level', 'timesince')
    list_filter = ('level', 'unread', )
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
        js = ('notifications/js/notifications.js',)

    def read(self, instance):
        return not instance.unread

    read.boolean = True
    read.short_description = _('read')

    actions = ['mark_as_read']

    def mark_as_read(self, request, queryset):
        result = queryset.filter(unread=True).update(unread=False)
        if result == 1:
            bit = '1 notification was'
        else:
            bit = '{0} notifications were'.format(result)
        message = '{0} marked as read.'.format(bit)
        self.message_user(request, _(message))
        Notification.invalidate_cache(request.user)

    mark_as_read.short_description = _('Mark selected notifications as read')

    def get_queryset(self, request):
        return self.model.objects.filter(recipient=request.user)

    def get_readonly_fields(self, request, obj=None):
        return self.fields or [f.name for f in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def render_change_form(self, request, context, add=False, change=True, form_url='', obj=None):
        if obj and obj.unread:
            obj.unread = False
            obj.save()
        # disable save buttons
        context.update({
            'add': False,
            'has_add_permission': False,
            'show_delete_link': True,
            'show_save_as_new': False,
            'show_save_and_add_another': False,
            'show_save_and_continue': False,
            'show_save': False
        })
        return super(NotificationAdmin, self).render_change_form(request, context, add=add,
                                                                 change=change, form_url=form_url, obj=obj)


class NotificationUserInline(AlwaysHasChangedMixin, admin.StackedInline):
    model = NotificationUser
    fields = ('receive', 'email')


UserAdmin.inlines.insert(len(UserAdmin.inlines) - 1,
                         NotificationUserInline)
