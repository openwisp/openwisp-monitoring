from django.contrib import admin
from openwisp_monitoring.check.admin import CheckAdmin  # noqa

from .models import DetailsModel

admin.site.register(DetailsModel)
