from swapper import load_model

from openwisp_users.api.filters import OrganizationManagedFilter

Device = load_model('config', 'Device')


class MonitoringDeviceFilter(OrganizationManagedFilter):
    class Meta(OrganizationManagedFilter.Meta):
        model = Device
        fields = OrganizationManagedFilter.Meta.fields + ['monitoring__status']
