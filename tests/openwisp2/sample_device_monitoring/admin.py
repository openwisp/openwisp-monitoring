from django.contrib import admin
from django.urls import reverse
from openwisp_monitoring.device import settings as app_settings
from openwisp_monitoring.device.base.admin import AbstractDeviceAdmin
from openwisp_monitoring.device.models import DeviceData
from openwisp_monitoring.monitoring.admin import MetricAdmin
from openwisp_monitoring.monitoring.models import Graph

from openwisp_controller.config.models import Device


class DeviceAdmin(AbstractDeviceAdmin):
    def get_extra_context(self, pk=None):
        ctx = super(DeviceAdmin, self).get_extra_context(pk)
        if pk:
            device_data = DeviceData(pk=pk)
            api_url = reverse('monitoring:api_device_metric', args=[pk])
            ctx.update(
                {
                    'device_data': device_data.data_user_friendly,
                    'api_url': api_url,
                    'default_time': Graph.DEFAULT_TIME,
                    'MAC_VENDOR_DETECTION': app_settings.MAC_VENDOR_DETECTION,
                }
            )
        return ctx


DeviceAdmin.Media.js += MetricAdmin.Media.js + ('monitoring/js/percircle.js',)
DeviceAdmin.Media.css['all'] += (
    'monitoring/css/percircle.css',
) + MetricAdmin.Media.css['all']

DeviceAdmin.list_display.insert(
    DeviceAdmin.list_display.index('config_status'), 'health_status'
)
DeviceAdmin.list_select_related += ('monitoring',)
DeviceAdmin.list_filter.insert(
    0, 'monitoring__status',
)
DeviceAdmin.fields.insert(DeviceAdmin.fields.index('last_ip'), 'health_status')
DeviceAdmin.readonly_fields.append('health_status')

admin.site.unregister(Device)
admin.site.register(Device, DeviceAdmin)
