import json
import logging

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
        device = self.related_object
        device_connection = self._get_device_connection(device)
        if not device_connection:
            logger.warning(
                f'DeviceConnection is not properly set for "{device}", iperf check skipped!'
            )
            return
        # The DeviceConnection could fail if the management tunnel is down.
        if not device_connection.connect():
            logger.warning(
                f'Failed to get a working DeviceConnection for "{device}", iperf check skipped!'
            )
            return
        servers = self._get_iperf_servers(device.organization.id)

        # TCP mode
        command = f'iperf3 -c {servers[0]} -J'
        res, exit_code = self._exec_command(device_connection, command)
        result_tcp = self._get_iperf_result(res, exit_code, device, mode='TCP')

        # UDP mode
        command = f'iperf3 -c {servers[0]} -u -J'
        res, exit_code = self._exec_command(device_connection, command)
        result_udp = self._get_iperf_result(res, exit_code, device, mode='UDP')

        if store:
            # Store iperf_result field 1 if any mode passes, store 0 when both fails
            iperf_result = result_tcp['iperf_result'] | result_udp['iperf_result']
            self.store_result(
                {**result_tcp, **result_udp, 'iperf_result': iperf_result}
            )
        device_connection.disconnect()
        return {**result_tcp, **result_udp, 'iperf_result': iperf_result}

    def _get_device_connection(self, device):
        """
        Returns an active SSH DeviceConnection for a device.
        """
        openwrt_ssh = UPDATE_STRATEGIES[0][0]
        device_connection = DeviceConnection.objects.filter(
            device_id=device.id,
            update_strategy=openwrt_ssh,
            enabled=True,
            is_working=True,
        ).first()
        return device_connection

    def _get_iperf_servers(self, organization_id):
        """
        Get iperf test servers
        """
        org_servers = app_settings.IPERF_SERVERS.get(str(organization_id))
        return org_servers

    def _exec_command(self, dc, command):
        """
        Executes device command
        """
        return dc.connector_instance.exec_command(command, raise_unexpected_exit=False)

    def _get_iperf_result(self, res, exit_code, device, mode):
        """
        Get iperf test result
        """

        res_dict = json.loads(res)
        if mode == 'TCP':
            if exit_code != 0:
                logger.warning(
                    f'Iperf check failed for "{device}", {res_dict["error"]}'
                )
                return {
                    'iperf_result': 0,
                    'sent_bps': 0.0,
                    'received_bps': 0.0,
                    'sent_bytes': 0.0,
                    'received_bytes': 0.0,
                    'retransmits': 0,
                }
            else:
                # Gbps = Gigabits per second
                # GB = GigaBytes
                # Todo : Remove below coversion once
                # https://github.com/openwisp/openwisp-monitoring/pull/397 get merged
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
                return {
                    'iperf_result': 1,
                    'sent_bps': round(sent_Gbps, 2),
                    'received_bps': round(received_Gbps, 2),
                    'sent_bytes': round(sent_bytes_GB, 2),
                    'received_bytes': round(received_bytes_GB, 2),
                    'retransmits': retransmits,
                }

        elif mode == 'UDP':
            if exit_code != 0:
                logger.warning(
                    f'Iperf check failed for "{device}", {res_dict["error"]}'
                )
                return {
                    'iperf_result': 0,
                    'jitter': 0.0,
                    'packets': 0,
                    'lost_packets': 0,
                    'lost_percent': 0.0,
                }
            else:
                jitter_ms = res_dict['end']['sum']['jitter_ms']
                packets = res_dict['end']['sum']['packets']
                lost_packets = res_dict['end']['sum']['lost_packets']
                lost_percent = float(res_dict['end']['sum']['lost_percent'])
                return {
                    'iperf_result': 1,
                    'jitter': round(jitter_ms, 2),
                    'packets': packets,
                    'lost_packets': lost_packets,
                    'lost_percent': round(lost_percent, 2),
                }

    def store_result(self, result):
        """
        store result in the DB
        """
        metric = self._get_metric()
        copied = result.copy()
        iperf_result = copied.pop('iperf_result')
        metric.write(iperf_result, extra_values=copied)

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
