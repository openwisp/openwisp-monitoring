from django.contrib import admin
from openwisp_monitoring.check.base.admin import AbstractCheckAdmin
from swapper import load_model

Check = load_model('sample_check', 'Check')


@admin.register(Check)
class CheckAdmin(AbstractCheckAdmin):
    pass
