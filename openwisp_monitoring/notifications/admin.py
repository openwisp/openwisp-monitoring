from django.contrib import admin
from django.urls import NoReverseMatch, reverse
from django.utils.html import format_html
from django.utils.translation import ugettext_lazy as _

from openwisp_users.admin import UserAdmin
from openwisp_utils.admin import AlwaysHasChangedMixin

from .models import Notification, NotificationUser


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    raw_id_fields = ('recipient',)
    readonly_fields = [
        'action_object_link',
        'actor_object_link',
        'target_object_link',
        'related_object',
    ]
    list_display = ('description', 'read', 'level', 'timesince')
    list_filter = (
        'level',
        'unread',
    )
    fieldsets = (
        (
            None,
            {
                'fields': (
                    'timestamp',
                    'level',
                    'description',
                    'related_object',
                    'emailed',
                )
            },
        ),
        (
            _('Advanced options'),
            {
                'classes': ('collapse',),
                'fields': (
                    'actor_content_type',
                    'actor_object_link',
                    'action_object_content_type',
                    'action_object_link',
                    'target_content_type',
                    'target_object_link',
                    'data',
                ),
            },
        ),
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

    def _get_link(self, obj, field, html=True):
        content_type = getattr(obj, f'{field}_content_type', None)
        object_id = getattr(obj, f'{field}_object_id', None)
        try:
            url = reverse(
                f'admin:{content_type.app_label}_{content_type.model}_change',
                args=[object_id],
            )
            if not html:
                return url
            return format_html(
                f'<a href="{url}" id="{field}-object-url">{object_id}</a>'
            )
        except NoReverseMatch:
            return object_id
        except AttributeError:
            return '-'

    def actor_object_link(self, obj):
        return self._get_link(obj, field='actor')

    actor_object_link.short_description = _('Actor Object')

    def action_object_link(self, obj):
        return self._get_link(obj, field='action_object')

    action_object_link.short_description = _('Action Object')

    def target_object_link(self, obj):
        return self._get_link(obj, field='target')

    target_object_link.short_description = _('Target Object')

    def related_object(self, obj):
        target_object_url = self._get_link(obj, field='target', html=False)
        if target_object_url.startswith('/admin/'):
            return format_html(
                '<a href="{url}" id="related-object-url">{content_type}: {name}</a>',
                url=target_object_url,
                content_type=obj.target_content_type.model,
                name=obj.target,
            )
        return target_object_url

    related_object.short_description = _('Related Object')

    def get_queryset(self, request):
        return self.model.objects.filter(recipient=request.user)

    def get_readonly_fields(self, request, obj=None):
        fields = self.fields or [f.name for f in self.model._meta.fields]
        return fields + self.__class__.readonly_fields

    def has_add_permission(self, request):
        return False

    def render_change_form(
        self, request, context, add=False, change=True, form_url='', obj=None
    ):
        if obj and obj.unread:
            obj.unread = False
            obj.save()
        # disable save buttons
        context.update(
            {
                'add': False,
                'has_add_permission': False,
                'show_delete_link': True,
                'show_save_as_new': False,
                'show_save_and_add_another': False,
                'show_save_and_continue': False,
                'show_save': False,
            }
        )
        return super(NotificationAdmin, self).render_change_form(
            request, context, add=add, change=change, form_url=form_url, obj=obj
        )


class NotificationUserInline(AlwaysHasChangedMixin, admin.StackedInline):
    model = NotificationUser
    fields = ('receive', 'email')


UserAdmin.inlines.insert(len(UserAdmin.inlines) - 1, NotificationUserInline)
