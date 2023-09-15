from django.utils.translation import gettext_lazy as _
from django_filters import rest_framework as filters
from swapper import load_model

from openwisp_users.api.filters import (
    FilterDjangoByOrgManaged,
    OrganizationManagedFilter,
)

Device = load_model('config', 'Device')
WifiSession = load_model('device_monitoring', 'WifiSession')


class WifiSessionFilter(FilterDjangoByOrgManaged):
    class Meta:
        model = WifiSession
        fields = {
            'device__organization': ['exact'],
            'device': ['exact'],
            'device__group': ['exact'],
            'start_time': ['exact', 'gt', 'gte', 'lt', 'lte'],
            'stop_time': ['exact', 'gt', 'gte', 'lt', 'lte'],
        }


class MonitoringDeviceFilter(OrganizationManagedFilter):
    class Meta(OrganizationManagedFilter.Meta):
        model = Device
        fields = OrganizationManagedFilter.Meta.fields + ['monitoring__status']


class MonitoringNearbyDeviceFilter(OrganizationManagedFilter):
    distance__lte = filters.NumberFilter(
        label=_('Distance is less than or equal to'),
        field_name='distance',
        lookup_expr='lte',
    )
    model = filters.CharFilter(method='filter_model')

    class Meta(OrganizationManagedFilter.Meta):
        model = Device
        fields = OrganizationManagedFilter.Meta.fields + [
            'monitoring__status',
            'model',
        ]

    def filter_model(self, queryset, name, value):
        values = value.split('|')
        return queryset.filter(**{f"{name}__in": values})
