from openwisp_controller.config.admin import DeviceResource as BaseDeviceResource

# add monitoring status to the exportable fields of DeviceAdmin
# this list of field is defined here to facilitate integartion testing
# with other modules which may need to mock this before the admin is loaded
_exportable_fields = BaseDeviceResource.Meta.fields[:]  # copy
_exportable_fields.insert(
    _exportable_fields.index('config__status'), 'monitoring__status'
)
