import json

from django.core.exceptions import ObjectDoesNotExist
from swapper import load_model

from openwisp_controller.connection.settings import UPDATE_STRATEGIES

from .. import settings as app_settings
from .base import BaseCheck

Chart = load_model('monitoring', 'Chart')
Metric = load_model('monitoring', 'Metric')
Device = load_model('config', 'Device')
DeviceData = load_model('device_monitoring', 'DeviceData')
Credentials = load_model('connection', 'Credentials')
AlertSettings = load_model('monitoring', 'AlertSettings')
DeviceConnection = load_model('connection', 'DeviceConnection')


class Iperf(BaseCheck):
    def check(self, store=True):
        try:
            device = self.related_object
            device_connection = self._check_device_connection(device)
            if device_connection:
                device_connection.connect()
                print(f'--- [{self.related_object}] is connected! ---')
                servers = self._get_iperf_servers(device.organization.id)
                command = f'iperf3 -c {servers[0]} -J'
                res, exit_code = device_connection.connector_instance.exec_command(
                    command, raise_unexpected_exit=False
                )
                if exit_code != 0:
                    print('---- Command Failed ----')
                    if store:
                        self.store_result(
                            {
                                'iperf_result': 0,
                                'sum_sent_bps': 0.0,
                                'sum_rec_bps': 0.0,
                                'sum_sent_bytes': 0.0,
                                'sum_rec_bytes': 0.0,
                                'sum_sent_retransmits': 0,
                            }
                        )
                    return
                else:
                    result_dict = self._get_iperf_result(res)
                    print('---- Command Output ----')
                    print(result_dict)
                    if store:
                        self.store_result(result_dict)
                    return result_dict
            else:
                print(
                    f'{self.related_object}: connection not properly set, Iperf skipped!'
                )
                return
        # If device have not active connection warning logged (return)
        except ObjectDoesNotExist:
            print(f'{self.related_object}: has no active connection, Iperf skipped!')
            return

    def _check_device_connection(self, device):
        """
        Check device has an active connection with right update_strategy(ssh)
        """
        openwrt_ssh = UPDATE_STRATEGIES[0][0]
        device_connection = DeviceConnection.objects.get(device_id=device.id)
        if device_connection.update_strategy == openwrt_ssh:
            if device_connection.enabled and device_connection.is_working:
                return device_connection
            else:
                return False
        else:
            return False

    def _get_iperf_servers(self, organization):
        """
        Get iperf test servers
        """
        org_servers = app_settings.IPERF_SERVERS.get(str(organization))
        return org_servers

    def _get_iperf_result(self, res, mode=None):
        """
        Get iperf test result
        """
        res_dict = json.loads(res)
        if mode is None:
            result = {
                'iperf_result': 1,
                'sum_sent_bps': round(
                    res_dict['end']['sum_sent']['bits_per_second'] / 1000000000, 2
                ),
                'sum_rec_bps': round(
                    res_dict['end']['sum_received']['bits_per_second'] / 1000000000, 2
                ),
                'sum_sent_bytes': round(
                    res_dict['end']['sum_sent']['bytes'] / 1000000000, 2
                ),
                'sum_rec_bytes': round(
                    res_dict['end']['sum_received']['bytes'] / 1000000000, 2
                ),
                'sum_sent_retransmits': res_dict['end']['sum_sent']['retransmits'],
            }
            return result
        # For UDP
        else:
            pass

    def store_result(self, result):
        """
        store result in the DB
        """
        pass

    def _get_metric(self):
        """
        Gets or creates metric
        """
        pass

    def _create_charts(self, metric):
        """
        Creates iperf related charts (Bandwith/Jitter)
        """
        pass

    def _create_alert_settings(self, metric):
        pass
