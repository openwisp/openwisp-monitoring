from django.contrib import admin
from django.contrib.admin.templatetags.admin_static import static
from django.urls import reverse

from openwisp_controller.config.admin import DeviceAdmin as BaseDeviceAdmin
from openwisp_controller.config.models import Device

from ..monitoring.admin import MetricAdmin
from ..monitoring.models import Graph
from .models import DeviceData


class DeviceAdmin(BaseDeviceAdmin):
    def get_extra_context(self, pk=None):
        ctx = super(DeviceAdmin, self).get_extra_context(pk)
        if pk:
            device_data = DeviceData(pk=pk)
            data = device_data.data and device_data.json(indent=4)
            api_url = reverse('monitoring:api_device_metric', args=[pk])
            ctx.update({
                'device_data': data,
                'api_url': api_url,
                'default_time': Graph.DEFAUT_TIME
            })
        return ctx


DeviceAdmin.Media.js += MetricAdmin.Media.js
DeviceAdmin.Media.css['all'] += (static('monitoring/css/monitoring.css'),)


admin.site.unregister(Device)
admin.site.register(Device, DeviceAdmin)
