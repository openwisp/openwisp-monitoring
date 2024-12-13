from django.db.models.signals import post_save
from swapper import load_model

from ..base.models import auto_wifi_client_check_receiver

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
        post_save.connect(
            auto_wifi_client_check_receiver,
            sender=Device,
            dispatch_uid='auto_wifi_clients_check',
        )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        post_save.disconnect(
            auto_wifi_client_check_receiver,
            sender=Device,
            dispatch_uid='auto_wifi_clients_check',
        )
