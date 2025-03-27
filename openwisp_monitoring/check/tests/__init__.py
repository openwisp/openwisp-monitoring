from swapper import load_model

from .. import settings as app_settings

Device = load_model('config', 'Device')

_FPING_REACHABLE = (
    '',
    bytes(
        '10.40.0.1 : xmt/rcv/%loss = 5/5/0%, min/avg/max = 0.04/0.08/0.15',
        encoding='utf8',
    ),
)

_FPING_UNREACHABLE = (
    '',
    bytes('192.168.255.255 : xmt/rcv/%loss = 3/0/100%', encoding='utf8'),
)


class AutoWifiClientCheck(object):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._auto_wifi_clients_check = app_settings.AUTO_WIFI_CLIENTS_CHECK
        app_settings.AUTO_WIFI_CLIENTS_CHECK = True

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        app_settings.AUTO_WIFI_CLIENTS_CHECK = cls._auto_wifi_clients_check


class AutoDataCollectedCheck(object):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._auto_data_collected_check = app_settings.AUTO_DATA_COLLECTED_CHECK
        app_settings.AUTO_DATA_COLLECTED_CHECK = True

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        app_settings.AUTO_DATA_COLLECTED_CHECK = cls._auto_data_collected_check
