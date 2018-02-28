from django.contrib import admin
from django.contrib.contenttypes.models import ContentType

from openwisp_controller.config.admin import DeviceAdmin as BaseDeviceAdmin
from openwisp_controller.config.models import Device

from ..monitoring.admin import MetricAdmin
from ..monitoring.models import Graph
from .models import DeviceData


class DeviceAdmin(BaseDeviceAdmin):
    def get_extra_context(self, pk=None):
        ctx = super(DeviceAdmin, self).get_extra_context(pk)
        if pk:
            ct = ContentType.objects.get(model=self.model.__name__.lower(),
                                         app_label=self.model._meta.app_label)
            graphs = Graph.objects.filter(metric__object_id=pk,
                                          metric__content_type=ct)
            device_data = DeviceData(pk=pk)
            data = device_data.data and device_data.json(indent=4)
            ctx.update({
                'graphs': graphs,
                'device_data': data
            })
        return ctx


DeviceAdmin.Media.js += MetricAdmin.Media.js


admin.site.unregister(Device)
admin.site.register(Device, DeviceAdmin)
