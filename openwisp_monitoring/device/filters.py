from django.utils.translation import gettext_lazy as _
from swapper import load_model

from openwisp_users.multitenancy import MultitenantRelatedOrgFilter
from openwisp_utils.admin_theme.filters import AutocompleteFilter

Device = load_model('config', 'Device')


class DeviceOrganizationFilter(MultitenantRelatedOrgFilter):
    rel_model = Device
    parameter_name = 'device__organization'


class DeviceGroupFilter(AutocompleteFilter):
    field_name = 'group'
    parameter_name = 'device__group'
    title = _('group')
    rel_model = Device


class DeviceFilter(AutocompleteFilter):
    field_name = 'device'
    parameter_name = 'device'
    title = _('device')
