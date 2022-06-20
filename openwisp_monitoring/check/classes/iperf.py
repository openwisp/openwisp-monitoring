import json
import logging

from django.core.exceptions import ObjectDoesNotExist
from swapper import load_model

from openwisp_controller.connection.settings import UPDATE_STRATEGIES

from .. import settings as app_settings
from .base import BaseCheck

logger = logging.getLogger(__name__)

Chart = load_model('monitoring', 'Chart')
Metric = load_model('monitoring', 'Metric')
Device = load_model('config', 'Device')
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
                servers = self._get_iperf_servers(device.organization.id)
                command = f'iperf3 -c {servers[0]} -J'
                res, exit_code = device_connection.connector_instance.exec_command(
                    command, raise_unexpected_exit=False
                )
                if store and exit_code != 0:
                    self.store_result_fail()
                    device_connection.disconnect()
                    return
                else:
                    result_dict_tcp = self._get_iperf_result(res, mode='TCP')
                    # UDP
                    command = f'iperf3 -c {servers[0]} -u -J'
                    res, exit_code = device_connection.connector_instance.exec_command(
                        command, raise_unexpected_exit=False
                    )
                    if store and exit_code != 0:
                        self.store_result_fail()
                        device_connection.disconnect()
                        return
                    else:
                        result_dict_udp = self._get_iperf_result(res, mode='UDP')
                        if store:
                            self.store_result({**result_dict_tcp, **result_dict_udp})
                    device_connection.disconnect()
                    return {**result_dict_tcp, **result_dict_udp}
            else:
                logger.warning(f'{device}: connection not properly set, Iperf skipped!')
                return
        # If device have not active connection warning logged (return)
        except ObjectDoesNotExist:
            logger.warning(f'{device}: connection not properly set, Iperf skipped!')
            return

    def _check_device_connection(self, device):
        """
        Check device has an active connection with right update_strategy(ssh)
        """
        openwrt_ssh = UPDATE_STRATEGIES[0][0]
        device_connection = DeviceConnection.objects.get(device_id=device.id)
        if device_connection.update_strategy == openwrt_ssh:
            if (
                device_connection.enabled
                and device_connection.is_working
                and device.monitoring.status in ['ok', 'problem']
            ):
                return device_connection
            else:
                return False
        else:
            return False

    def _get_iperf_servers(self, organization_id):
        """
        Get iperf test servers
        """
        org_servers = app_settings.IPERF_SERVERS.get(str(organization_id))
        return org_servers

    def _get_iperf_result(self, res, mode):
        """
        Get iperf test result
        """
        res_dict = json.loads(res)
        if mode == 'TCP':
            # Gbps = Gigabits per second
            # GB = GigaBytes
            sent_json = res_dict['end']['sum_sent']
            recv_json = res_dict['end']['sum_received']
            sent_bytes = sent_json['bytes']
            sent_bytes_GB = sent_bytes / 1000000000
            sent_bps = sent_json['bits_per_second']
            sent_Gbps = sent_bps / 1000000000
            received_bytes = recv_json['bytes']
            received_bytes_GB = received_bytes / 1000000000
            received_bps = recv_json['bits_per_second']
            received_Gbps = received_bps / 1000000000
            retransmits = sent_json['retransmits']

            result = {
                'iperf_result': 1,
                'sent_bps': round(sent_Gbps, 2),
                'received_bps': round(received_Gbps, 2),
                'sent_bytes': round(sent_bytes_GB, 2),
                'received_bytes': round(received_bytes_GB, 2),
                'retransmits': retransmits,
            }
            return result
        # For UDP
        elif mode == 'UDP':
            jitter_ms = res_dict['end']['sum']['jitter_ms']
            packets = res_dict['end']['sum']['packets']
            lost_packets = res_dict['end']['sum']['lost_packets']
            lost_percent = float(res_dict['end']['sum']['lost_percent'])
            result = {
                'jitter': round(jitter_ms, 2),
                'packets': packets,
                'lost_packets': lost_packets,
                'lost_percent': round(lost_percent, 2),
            }
            return result

    def store_result(self, result):
        """
        store result in the DB
        """
        metric = self._get_metric()
        copied = result.copy()
        iperf_result = copied.pop('iperf_result')
        metric.write(iperf_result, extra_values=copied)

    def store_result_fail(self):
        """
        store fail result in the DB
        """
        self.store_result(
            {
                'iperf_result': 0,
                'sent_bps': 0.0,
                'received_bps': 0.0,
                'sent_bytes': 0.0,
                'received_bytes': 0.0,
                'retransmits': 0,
                'jitter': 0.0,
                'packets': 0,
                'lost_packets': 0,
                'lost_percent': 0.0,
            }
        )

    def _get_metric(self):
        """
        Gets or creates metric
        """
        metric, created = self._get_or_create_metric()
        if created:
            self._create_charts(metric)
        return metric

    def _create_charts(self, metric):
        """
        Creates iperf related charts (Bandwith/Jitter)
        """
        charts = [
            'bitrate',
            'transfer',
            'retransmits',
            'jitter',
            'datagram',
            'datagram_loss',
        ]
        for chart in charts:
            chart = Chart(metric=metric, configuration=chart)
            chart.full_clean()
            chart.save()

    def _create_alert_settings(self, metric):
        pass
