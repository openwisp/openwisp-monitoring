from django.contrib import admin
from swapper import load_model

from openwisp_utils.admin import TimeReadonlyAdminMixin

Check = load_model('check', 'Check')


@admin.register(Check)
class CheckAdmin(TimeReadonlyAdminMixin, admin.ModelAdmin):
    list_display = ['__str__', 'check_type', 'created', 'modified']
    search_fields = ['name', 'object_id']
    # TODO: filters
    save_on_top = True
