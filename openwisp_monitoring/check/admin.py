from django.contrib import admin

from openwisp_utils.admin import TimeReadonlyAdminMixin

from .models import Check


@admin.register(Check)
class CheckAdmin(TimeReadonlyAdminMixin, admin.ModelAdmin):
    list_display = ('__str__', 'check', 'created', 'modified')
    search_fields = ('name', 'object_id')
    # TODO: filters
    save_on_top = True
