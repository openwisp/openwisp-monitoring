import logging
from json import loads
from json.decoder import JSONDecodeError

from django.core.exceptions import ValidationError
from jsonschema import draft7_format_checker, validate
from jsonschema.exceptions import ValidationError as SchemaError
from swapper import load_model

from openwisp_controller.connection.settings import UPDATE_STRATEGIES
from openwisp_utils.utils import deep_merge_dicts

from .. import settings as app_settings
from .base import BaseCheck

logger = logging.getLogger(__name__)

Chart = load_model('monitoring', 'Chart')
Metric = load_model('monitoring', 'Metric')
AlertSettings = load_model('monitoring', 'AlertSettings')
DeviceConnection = load_model('connection', 'DeviceConnection')

DEFAULT_IPERF_CHECK_CONFIG = {
    'port': {
        'type': 'integer',
        'default': 5201,
        # max, min port chosen from iperf3 docs
        'minimum': 1,
        'maximum': 65535,
    },
    'time': {
        'type': 'integer',
        # Sets the interval time in seconds
        # between periodic bandwidth, jitter, and loss reports.
        'default': 10,
        'minimum': 1,
        # arbitrary chosen to avoid slowing down the queue (30min)
        'maximum': 1800,
    },
}


def get_iperf_schema():
    schema = {
        '$schema': 'http://json-schema.org/draft-07/schema#',
        'type': 'object',
        'additionalProperties': False,
    }
    schema['properties'] = deep_merge_dicts(
        DEFAULT_IPERF_CHECK_CONFIG, app_settings.IPERF_CHECK_CONFIG
    )
    return schema


class Iperf(BaseCheck):

    schema = get_iperf_schema()

    def validate_params(self):
        try:
            validate(self.params, self.schema, format_checker=draft7_format_checker)
        except SchemaError as e:
            message = 'Invalid param'
            path = '/'.join(e.path)
            if path:
                message = '{0} in "{1}"'.format(message, path)
            message = '{0}: {1}'.format(message, e.message)
            raise ValidationError({'params': message}) from e

    def check(self, store=True):
        port = self._get_param('port')
        time = self._get_param('time')
        device = self.related_object
        device_connection = self._get_device_connection(device)
        if not device_connection:
            logger.warning(
                f'Failed to get a working DeviceConnection for "{device}", iperf check skipped!'
            )
            return
        # The DeviceConnection could fail if the management tunnel is down.
        if not self._connect(device_connection):
            logger.warning(
                f'DeviceConnection for "{device}" is not working, iperf check skipped!'
            )
            return
        servers = self._get_iperf_servers(device.organization.id)

        # TCP mode
        command = f'iperf3 -c {servers[0]} -p {port} -t {time} -J'
        result, exit_code = self._exec_command(device_connection, command)

        # Exit code 127 : command doesn't exist
        if exit_code == 127:
            logger.warning(
                f'Iperf3 is not installed on the "{device}", error - {result.strip()}'
            )
            return

        result_tcp = self._get_iperf_result(result, exit_code, device, mode='TCP')

        # UDP mode
        command = f'iperf3 -c {servers[0]} -p {port} -t {time} -u -J'
        result, exit_code = self._exec_command(device_connection, command)
        result_udp = self._get_iperf_result(result, exit_code, device, mode='UDP')

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

    def _connect(self, dc):
        """
        Connects device returns its working status (easier to mock)
        """
        return dc.connect()

    def _get_param(self, param):
        """
        Gets specified param or its default value according to the schema
        """
        return self.params.get(param, self.schema['properties'][param]['default'])

    def _get_iperf_result(self, result, exit_code, device, mode):
        """
        Returns iperf test result
        """

        try:
            result = loads(result)
        except JSONDecodeError:
            # Errors other than iperf3 test errors
            result = {'error': f'error - {result.strip()}'}

        if mode == 'TCP':
            if exit_code != 0:
                logger.warning(f'Iperf check failed for "{device}", {result["error"]}')
                return {
                    'iperf_result': 0,
                    'sent_bps_tcp': 0.0,
                    'received_bps_tcp': 0.0,
                    'sent_bytes_tcp': 0,
                    'received_bytes_tcp': 0,
                    'retransmits': 0,
                }
            else:
                sent = result['end']['sum_sent']
                received = result['end']['sum_received']
                return {
                    'iperf_result': 1,
                    'sent_bps_tcp': float(sent['bits_per_second']),
                    'received_bps_tcp': float(received['bits_per_second']),
                    'sent_bytes_tcp': sent['bytes'],
                    'received_bytes_tcp': received['bytes'],
                    'retransmits': sent['retransmits'],
                }

        elif mode == 'UDP':
            if exit_code != 0:
                logger.warning(f'Iperf check failed for "{device}", {result["error"]}')
                return {
                    'iperf_result': 0,
                    'sent_bps_udp': 0.0,
                    'sent_bytes_udp': 0,
                    'jitter': 0.0,
                    'total_packets': 0,
                    'lost_packets': 0,
                    'lost_percent': 0.0,
                }
            else:
                return {
                    'iperf_result': 1,
                    'sent_bps_udp': float(result['end']['sum']['bits_per_second']),
                    'sent_bytes_udp': result['end']['sum']['bytes'],
                    'jitter': float(result['end']['sum']['jitter_ms']),
                    'total_packets': result['end']['sum']['packets'],
                    'lost_packets': result['end']['sum']['lost_packets'],
                    'lost_percent': float(result['end']['sum']['lost_percent']),
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
            self._create_alert_settings(metric)
            self._create_charts(metric)
        return metric

    def _create_charts(self, metric):
        """
        Creates iperf related charts (Bandwith/Jitter)
        """
        charts = [
            'bandwidth_tcp',
            'transfer_tcp',
            'retransmits',
            'bandwidth_udp',
            'transfer_udp',
            'jitter',
            'datagram',
            'datagram_loss',
        ]
        for chart in charts:
            chart = Chart(metric=metric, configuration=chart)
            chart.full_clean()
            chart.save()

    def _create_alert_settings(self, metric):
        alert_settings = AlertSettings(metric=metric)
        alert_settings.full_clean()
        alert_settings.save()
