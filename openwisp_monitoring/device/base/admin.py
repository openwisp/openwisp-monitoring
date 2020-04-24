from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _

from openwisp_controller.config.admin import DeviceAdmin as BaseDeviceAdmin

from ..models import DeviceMonitoring


class AbstractDeviceAdmin(BaseDeviceAdmin):
    def health_status(self, obj):
        return format_html(
            mark_safe('<span class="health-{0}">{1}</span>'),
            obj.monitoring.status,
            obj.monitoring.get_status_display(),
        )

    health_status.short_description = _('health status')

    def get_form(self, request, obj=None, **kwargs):
        """
        Adds the help_text of DeviceMonitoring.status field
        """
        health_status = DeviceMonitoring._meta.get_field('status').help_text
        kwargs.update(
            {'help_texts': {'health_status': health_status.replace('\n', '<br>')}}
        )
        return super().get_form(request, obj, **kwargs)
