from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _
from swapper import load_model

from openwisp_monitoring.monitoring.configuration import get_metric_configuration
from openwisp_users.multitenancy import MultitenantOrgFilter
from openwisp_utils.admin_theme.filters import AutocompleteFilter, SubFilterMixin

Device = load_model("config", "Device")
Metric = load_model("monitoring", "Metric")


class UnhealthyMetricFilter(SubFilterMixin, admin.SimpleListFilter):
    parameter_name = "unhealthy_metric"
    title = _("by problematic metric")
    parent_parameter_name = "monitoring__status"
    parent_active_values = ("problem",)

    def lookups(self, request, model_admin):
        choices = []
        for key, config in sorted(get_metric_configuration().items()):
            if "alert_settings" in config:
                name = config.get("label", key)
                choices.append((key, str(name)))
        return choices

    def filter_queryset(self, request, queryset):
        if self.value():
            unhealthy_device_ids = list(
                Metric.objects.filter(
                    is_healthy=False,
                    content_type=ContentType.objects.get_for_model(Device),
                    configuration=self.value(),
                ).values_list("object_id", flat=True)
            )
            return queryset.filter(id__in=unhealthy_device_ids)
        return queryset


class DeviceOrganizationFilter(MultitenantOrgFilter):
    rel_model = Device
    parameter_name = "device__organization"


class DeviceGroupFilter(AutocompleteFilter):
    field_name = "group"
    parameter_name = "device__group"
    title = _("group")
    rel_model = Device


class DeviceFilter(AutocompleteFilter):
    field_name = "device"
    parameter_name = "device"
    title = _("device")
