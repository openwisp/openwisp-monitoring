from django.contrib import admin
from openwisp_monitoring.device.admin import DeviceAdmin  # noqa

from .models import DetailsModel

admin.site.register(DetailsModel)
