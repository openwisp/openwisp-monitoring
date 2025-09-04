from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from django_filters import rest_framework as filters
from swapper import load_model

from openwisp_users.api.filters import (
    FilterDjangoByOrgManaged,
    OrganizationManagedFilter,
)

Device = load_model("config", "Device")
WifiSession = load_model("device_monitoring", "WifiSession")
DeviceMonitoring = load_model("device_monitoring", "DeviceMonitoring")


class WifiSessionFilter(FilterDjangoByOrgManaged):
    class Meta:
        model = WifiSession
        fields = {
            "device__organization": ["exact"],
            "device": ["exact"],
            "device__group": ["exact"],
            "start_time": ["exact", "gt", "gte", "lt", "lte"],
            "stop_time": ["exact", "gt", "gte", "lt", "lte", "isnull"],
        }


class MonitoringLocationDeviceFilter(filters.FilterSet):
    search = filters.CharFilter(method="filter_search")
    status = filters.MultipleChoiceFilter(
        field_name="monitoring__status",
        choices=DeviceMonitoring.STATUS,
    )

    def filter_search(self, queryset, name, value):
        value = value.strip()
        return queryset.filter(
            Q(name__icontains=value) | Q(mac_address__icontains=value)
        )

    class Meta:
        model = Device
        fields = ["search", "status"]


class MonitoringDeviceFilter(OrganizationManagedFilter):
    class Meta(OrganizationManagedFilter.Meta):
        model = Device
        fields = OrganizationManagedFilter.Meta.fields + ["monitoring__status"]


class MonitoringNearbyDeviceFilter(OrganizationManagedFilter):
    distance__lte = filters.NumberFilter(
        label=_("Distance is less than or equal to"),
        field_name="distance",
        lookup_expr="lte",
    )
    model = filters.CharFilter(method="filter_model")

    class Meta(OrganizationManagedFilter.Meta):
        model = Device
        fields = OrganizationManagedFilter.Meta.fields + [
            "monitoring__status",
            "model",
        ]

    def filter_model(self, queryset, name, value):
        values = value.split("|")
        return queryset.filter(**{f"{name}__in": values})
