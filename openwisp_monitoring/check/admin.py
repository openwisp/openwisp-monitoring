from django.contrib import admin

from .base.admin import AbstractCheckAdmin
from .models import Check


@admin.register(Check)
class CheckAdmin(AbstractCheckAdmin):
    model = Check
