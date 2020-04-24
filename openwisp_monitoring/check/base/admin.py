from django.contrib import admin

from openwisp_utils.admin import TimeReadonlyAdminMixin


class AbstractCheckAdmin(TimeReadonlyAdminMixin, admin.ModelAdmin):
    list_display = ('__str__', 'check', 'created', 'modified')
    search_fields = ('name', 'object_id')
    # TODO: filters
    save_on_top = True
