from django.conf import settings
from django.utils.translation import gettext_lazy as _

from ..settings import get_settings_value

CHECK_CLASSES = get_settings_value(
    'CHECK_CLASSES',
    (
        ('openwisp_monitoring.check.classes.Ping', _('Ping'), 'AUTO_PING'),
        (
            'openwisp_monitoring.check.classes.ConfigApplied',
            _('Configuration Applied'),
            'AUTO_CONFIG_CHECK',
        ),
        ('openwisp_monitoring.check.classes.Iperf3', 'Iperf3', 'AUTO_IPERF3'),
        (
            'openwisp_monitoring.check.classes.WifiClients',
            'WiFi Clients',
            'AUTO_WIFI_CLIENTS_CHECK',
        ),
        (
            'openwisp_monitoring.check.classes.DataCollected',
            'Monitoring Data Collected',
            'AUTO_DATA_COLLECTED_CHECK',
        ),
    ),
)

CHECK_CHOICES = []
CHECK_LIST = []
for class_string, name, setting_name in CHECK_CLASSES:
    CHECK_CHOICES.append((class_string, name))
    CHECK_LIST.append(class_string)

AUTO_PING = get_settings_value('AUTO_PING', True)
AUTO_CONFIG_CHECK = get_settings_value('AUTO_DEVICE_CONFIG_CHECK', True)
# If OPENWISP_MONITORING_MANAGEMENT_IP_ONLY is not configured, use
# OPENWISP_CONTROLLER_MANAGEMENT_IP_ONLY.
MANAGEMENT_IP_ONLY = get_settings_value(
    'MANAGEMENT_IP_ONLY',
    getattr(settings, 'OPENWISP_CONTROLLER_MANAGEMENT_IP_ONLY', True),
)
PING_CHECK_CONFIG = get_settings_value('PING_CHECK_CONFIG', {})
AUTO_WIFI_CLIENTS_CHECK = get_settings_value('AUTO_WIFI_CLIENTS_CHECK', False)
WIFI_CLIENTS_CHECK_SNOOZE_SCHEDULE = get_settings_value(
    'WIFI_CLIENTS_CHECK_SNOOZE_SCHEDULE', []
)
WIFI_CLIENTS_MAX_CHECK_INTERVAL = int(
    get_settings_value('WIFI_CLIENTS_MAX_CHECK_INTERVAL', 5)
)  # in minutes
WIFI_CLIENTS_MIN_CHECK_INTERVAL = int(
    get_settings_value('WIFI_CLIENTS_MIN_CHECK_INTERVAL', 4320)
)  # in minutes
AUTO_DATA_COLLECTED_CHECK = get_settings_value('AUTO_DATA_COLLECTED_CHECK', True)
DATA_COLLECTED_CHECK_INTERVAL = int(
    get_settings_value('DATA_COLLECTED_CHECK_INTERVAL', 60)
)  # in minutes
AUTO_IPERF3 = get_settings_value('AUTO_IPERF3', False)
IPERF3_CHECK_CONFIG = get_settings_value('IPERF3_CHECK_CONFIG', {})
IPERF3_CHECK_LOCK_EXPIRE = get_settings_value(
    'IPERF3_CHECK_LOCK_EXPIRE', 10 * 60
)  # 10 minutes arbitrarily chosen (must be longer than TCP + UDP test time)
IPERF3_CHECK_DELETE_RSA_KEY = get_settings_value('IPERF3_CHECK_DELETE_RSA_KEY', True)
CONFIG_CHECK_INTERVAL = int(
    get_settings_value('CONFIG_CHECK_INTERVAL', 5)
)  # in minutes
