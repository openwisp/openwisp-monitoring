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
