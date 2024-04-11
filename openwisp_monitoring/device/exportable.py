from import_export.fields import Field

from openwisp_controller.geo.exportable import GeoDeviceResource as BaseDeviceResource


class DeviceMonitoringResource(BaseDeviceResource):
    monitoring_status = Field(
        attribute='monitoring__status', column_name='monitoring_status', readonly=True
    )

    class Meta(BaseDeviceResource.Meta):
        fields = BaseDeviceResource.Meta.fields[:]  # copy
        # add monitoring status to the exportable fields of DeviceAdmin
        fields.insert(fields.index('config_status'), 'monitoring_status')
        export_order = fields


# this list of field is defined here to facilitate integartion testing
# with other modules which may need to mock this before the admin is loaded
_exportable_fields = DeviceMonitoringResource.Meta.fields
