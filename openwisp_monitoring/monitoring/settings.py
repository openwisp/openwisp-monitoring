from django.conf import settings
from django.utils.translation import ugettext_lazy as _

INFLUXDB_HOST = getattr(settings, 'INFLUXDB_HOST', 'localhost')
INFLUXDB_PORT = getattr(settings, 'INFLUXDB_PORT', '8086')
INFLUXDB_USER = getattr(settings, 'INFLUXDB_USER')
INFLUXDB_PASSWORD = getattr(settings, 'INFLUXDB_PASSWORD')
INFLUXDB_DATABASE = getattr(settings, 'INFLUXDB_DATABASE', 'openwisp2')

QUERY = getattr(settings, 'OPENWISP_MONITORING_CUSTOM_QUERY', (()))

# TODO: Need to add many more queries and give readable names to each
QUERY += (
    (
        "SELECT {field_name} FROM {key} WHERE time >= '{time}' AND "
        "content_type = '{content_type}' AND object_id = '{object_id}'",
        _('Default Query'),
    ),
    # Include query by printing them during testing
)
