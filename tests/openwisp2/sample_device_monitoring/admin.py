from django.contrib import admin
from openwisp_monitoring.device.admin import DeviceAdmin  # noqa

from openwisp_controller.config.models import Device

from .models import DetailsModel

admin.site.unregister(Device, DeviceAdmin)
admin.site.register(Device, DeviceAdmin, DetailsModel)
