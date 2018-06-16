from datetime import datetime

from dateutil.relativedelta import relativedelta
from django.contrib import admin
from django.contrib.admin.templatetags.admin_static import static
from django.urls import reverse
from pytz import timezone as tz

from openwisp_controller.config.admin import DeviceAdmin as BaseDeviceAdmin
from openwisp_controller.config.models import Device

from ..monitoring.admin import MetricAdmin
from ..monitoring.models import Graph
from .models import DeviceData


class DeviceAdmin(BaseDeviceAdmin):
    def get_device_data(self, data):
        if not data:
            return None
        if 'general' in data and 'local_time' in data['general']:
            local_time = data['general']['local_time']
            data['general']['local_time'] = datetime.fromtimestamp(local_time, tz=tz('UTC'))
        if 'general' in data and 'uptime' in data['general']:
            uptime = '{0.days} days, {0.hours} hours and {0.minutes} minutes'
            data['general']['uptime'] = uptime.format(relativedelta(seconds=data['general']['uptime']))
        if 'resources' in data and 'memory' in data['resources']:
            # convert bytes to megabytes
            MB = 1000000.0
            for key in data['resources']['memory'].keys():
                data['resources']['memory'][key] /= MB
        remove = []
        for interface in data.get('interfaces', []):
            # don't show interfaces if they don't have any useful info
            if len(interface.keys()) <= 2:
                remove.append(interface)
                continue
            # human readable mode
            interface['wireless']['mode'] = interface['wireless']['mode'].replace('_', ' ')
            # convert to GHz
            if 'wireless' in interface and 'frequency' in interface['wireless']:
                interface['wireless']['frequency'] /= 1000
        for interface in remove:
            data['interfaces'].remove(interface)
        return data

    def get_extra_context(self, pk=None):
        ctx = super(DeviceAdmin, self).get_extra_context(pk)
        if pk:
            device_data = DeviceData(pk=pk)
            api_url = reverse('monitoring:api_device_metric', args=[pk])
            ctx.update({
                'device_data': self.get_device_data(device_data.data),
                'api_url': api_url,
                'default_time': Graph.DEFAULT_TIME
            })
        return ctx


DeviceAdmin.Media.js += MetricAdmin.Media.js
DeviceAdmin.Media.css['all'] += (static('monitoring/css/monitoring.css'),)


admin.site.unregister(Device)
admin.site.register(Device, DeviceAdmin)
