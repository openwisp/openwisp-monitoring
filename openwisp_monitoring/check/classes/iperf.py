import logging
from functools import reduce
from json import loads
from json.decoder import JSONDecodeError

from django.core.exceptions import ValidationError
from jsonschema import draft7_format_checker, validate
from jsonschema.exceptions import ValidationError as SchemaError
from swapper import load_model

from openwisp_controller.connection.settings import UPDATE_STRATEGIES

from .. import settings as app_settings
from .base import BaseCheck

logger = logging.getLogger(__name__)

Chart = load_model('monitoring', 'Chart')
Metric = load_model('monitoring', 'Metric')
AlertSettings = load_model('monitoring', 'AlertSettings')
DeviceConnection = load_model('connection', 'DeviceConnection')

DEFAULT_IPERF_CHECK_CONFIG = {
    'host': {
        'type': 'array',
        'items': {
            'type': 'string',
        },
        'default': [],
    },
    # username, password max_length chosen from iperf3 docs to avoid iperf param errors
    'username': {'type': 'string', 'default': '', 'minLength': 1, 'maxLength': 20},
    'password': {'type': 'string', 'default': '', 'minLength': 1, 'maxLength': 20},
    'rsa_public_key': {
        'type': 'string',
        'default': '',
    },
    'client_options': {
        'type': 'object',
        'properties': {
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
                # between periodic bandwidth, jitter, and loss reports
                'default': 10,
                'minimum': 1,
                # arbitrary chosen to avoid slowing down the queue (30min)
                'maximum': 1800,
            },
            'bytes': {
                'type': 'string',
                # number of bytes to transmit (instead of 'time')
                # default to '' since we're using time for
                # the test end condition instead of bytes
                'default': '',
            },
            'blockcount': {
                'type': 'string',
                # number of blocks (packets) to transmit (instead of 'time' or 'bytes')
                # default to '' since we're using time for
                # the test end condition instead of blockcount
                'default': '',
            },
            'connect_timeout': {
                'type': 'integer',
                # set  timeout  for establishing the initial
                # control connection to the server, in milliseconds (ms)
                # providing a shorter value (ex. 1 ms) may
                # speed up detection of a down iperf3 server
                'default': 1,
                'minimum': 1,
                # arbitrary chosen to avoid slowing down the queue (1000 sec)
                'maximum': 1000000,
            },
            'tcp': {
                'type': 'object',
                'properties': {
                    'bitrate': {
                        'type': 'string',
                        # set target bitrate to n bits/sec
                        'default': '0',
                    },
                    'length': {
                        'type': 'string',
                        # length of buffer to read or write
                        # for TCP tests, the default value is 128KB
                        'default': '128K',
                    },
                },
            },
            'udp': {
                'type': 'object',
                'properties': {
                    'bitrate': {
                        'type': 'string',
                        # set target bitrate to n bits/sec
                        # 10 Mbps
                        'default': '30M',
                    },
                    'length': {
                        'type': 'string',
                        # iperf3 tries to dynamically determine a
                        # reasonable sending size based on the path MTU
                        # if that cannot be determined it uses 1460 bytes
                        'default': '',
                    },
                },
            },
        },
    },
}


def get_iperf_schema():
    schema = {
        '$schema': 'http://json-schema.org/draft-07/schema#',
        'type': 'object',
        'additionalProperties': True,
        'dependencies': {
            'username': ['password', 'rsa_public_key'],
            'password': ['username', 'rsa_public_key'],
            'rsa_public_key': ['username', 'password'],
        },
    }
    schema['properties'] = DEFAULT_IPERF_CHECK_CONFIG
    return schema


class Iperf(BaseCheck):

    schema = get_iperf_schema()

    def validate_params(self, params=None):
        try:
            if not params:
                params = self.params
            validate(params, self.schema, format_checker=draft7_format_checker)
        except SchemaError as e:
            message = 'Invalid param'
            path = '/'.join(e.path)
            if path:
                message = '{0} in "{1}"'.format(message, path)
            message = '{0}: {1}'.format(message, e.message)
            raise ValidationError({'params': message}) from e

    def check(self, store=True):
        iperf_config = app_settings.IPERF_CHECK_CONFIG
        if iperf_config:
            org_id = str(self.related_object.organization.id)
            self.validate_params(params=iperf_config[org_id])

        port = self._get_param(
            'client_options.port', 'client_options.properties.port.default'
        )
        time = self._get_param(
            'client_options.time', 'client_options.properties.time.default'
        )
        bytes = self._get_param(
            'client_options.bytes', 'client_options.properties.bytes.default'
        )
        blockcount = self._get_param(
            'client_options.blockcount', 'client_options.properties.blockcount.default'
        )
        ct = self._get_param(
            'client_options.connect_timeout',
            'client_options.properties.connect_timeout.default',
        )
        tcp_bitrate = self._get_param(
            'client_options.tcp.bitrate',
            'client_options.properties.tcp.properties.bitrate.default',
        )
        tcp_length = self._get_param(
            'client_options.tcp.length',
            'client_options.properties.tcp.properties.length.default',
        )
        udp_bitrate = self._get_param(
            'client_options.udp.bitrate',
            'client_options.properties.udp.properties.bitrate.default',
        )
        udp_length = self._get_param(
            'client_options.udp.length',
            'client_options.properties.udp.properties.length.default',
        )
        # by default we use 'time' param
        # for the iperf test end condition
        test_end_condition = f'-t {time}'
        # if 'bytes' present in config
        # use it instead of 'time'
        if bytes:
            test_end_condition = f'-n {bytes}'
        # if 'blockcount' present in config
        # use it instead of 'time' or 'bytes'
        if blockcount:
            test_end_condition = f'-k {blockcount}'
        username = self._get_param('username', 'username.default')
        device_connection = self._get_device_connection()
        if not device_connection:
            logger.warning(
                f'Failed to get a working DeviceConnection for "{self.related_object}", iperf check skipped!'
            )
            return
        # The DeviceConnection could fail if the management tunnel is down.
        if not self._connect(device_connection):
            logger.warning(
                f'DeviceConnection for "{self.related_object}" is not working, iperf check skipped!'
            )
            return
        server = self._get_iperf_servers()[0]
        command_tcp = f'iperf3 -c {server} -p {port} {test_end_condition} \
        --connect-timeout {ct} -b {tcp_bitrate} -l {tcp_length} -J'
        command_udp = f'iperf3 -c {server} -p {port} {test_end_condition} \
        --connect-timeout {ct} -b {udp_bitrate} -l {udp_length} -u -J'

        # All three parameters ie. username, password and rsa_public_key is required
        # for authentication to work, checking only username here
        if username:
            password = self._get_param('password', 'password.default')
            key = self._get_param('rsa_public_key', 'rsa_public_key.default')
            rsa_public_key = self._get_compelete_rsa_key(key)
            rsa_public_key_path = '/tmp/iperf-public-key.pem'

            command_tcp = f'echo "{rsa_public_key}" > {rsa_public_key_path} && \
            IPERF3_PASSWORD="{password}" iperf3 -c {server} -p {port} {test_end_condition} \
            --username "{username}" --rsa-public-key-path {rsa_public_key_path} \
            --connect-timeout {ct} -b {tcp_bitrate} -l {tcp_length} -J'

            command_udp = f'IPERF3_PASSWORD="{password}" iperf3 -c {server} -p {port} {test_end_condition} \
            --username "{username}" --rsa-public-key-path {rsa_public_key_path} \
            --connect-timeout {ct} -b {udp_bitrate} -l {udp_length} -u -J'

            # If IPERF_CHECK_DELETE_RSA_KEY, remove rsa_public_key from the device
            if app_settings.IPERF_CHECK_DELETE_RSA_KEY:
                command_udp = f'{command_udp} && rm {rsa_public_key_path}'

        # TCP mode
        result, exit_code = self._exec_command(device_connection, command_tcp)
        # Exit code 127 : command doesn't exist
        if exit_code == 127:
            logger.warning(
                f'Iperf3 is not installed on the "{self.related_object}", error - {result.strip()}'
            )
            return

        result_tcp = self._get_iperf_result(result, exit_code, mode='TCP')
        # UDP mode
        result, exit_code = self._exec_command(device_connection, command_udp)
        result_udp = self._get_iperf_result(result, exit_code, mode='UDP')
        result = {}
        if store and result_tcp and result_udp:
            # Store iperf_result field 1 if any mode passes, store 0 when both fails
            iperf_result = result_tcp['iperf_result'] | result_udp['iperf_result']
            result.update({**result_tcp, **result_udp, 'iperf_result': iperf_result})
            self.store_result(result)
        device_connection.disconnect()
        return result

    def _get_compelete_rsa_key(self, key):
        """
        Returns RSA key with proper format
        """
        pem_prefix = '-----BEGIN PUBLIC KEY-----\n'
        pem_suffix = '\n-----END PUBLIC KEY-----'
        key = key.strip()
        return f'{pem_prefix}{key}{pem_suffix}'

    def _get_device_connection(self):
        """
        Returns an active SSH DeviceConnection for a device
        """
        openwrt_ssh = UPDATE_STRATEGIES[0][0]
        device_connection = DeviceConnection.objects.filter(
            device_id=self.related_object.id,
            update_strategy=openwrt_ssh,
            enabled=True,
        ).first()
        return device_connection

    def _get_iperf_servers(self):
        """
        Get iperf test servers
        """
        org_servers = self._get_param('host', 'host.default')
        return org_servers

    def _exec_command(self, dc, command):
        """
        Executes device command (easier to mock)
        """
        return dc.connector_instance.exec_command(command, raise_unexpected_exit=False)

    def _connect(self, dc):
        """
        Connects device returns its working status (easier to mock)
        """
        return dc.connect()

    def _deep_get(self, dictionary, keys, default=None):
        """
        Returns dict value using dot_key string ie.key1.key2_nested.key3_nested
        if found otherwise returns default
        """
        return reduce(
            lambda d, key: d.get(key, default) if isinstance(d, dict) else default,
            keys.split("."),
            dictionary,
        )

    def _get_param(self, conf_key, default_conf_key):
        """
        Returns specified param or its default value according to the schema
        """
        org_id = str(self.related_object.organization.id)
        iperf_config = app_settings.IPERF_CHECK_CONFIG

        if self.params:
            check_params = self._deep_get(self.params, conf_key)
            if check_params:
                return check_params

        if iperf_config:
            iperf_config = iperf_config[org_id]
            iperf_config_param = self._deep_get(iperf_config, conf_key)
            if iperf_config_param:
                return iperf_config_param

        return self._deep_get(DEFAULT_IPERF_CHECK_CONFIG, default_conf_key)

    def _get_iperf_result(self, result, exit_code, mode):
        """
        Returns iperf test result
        """
        try:
            result = loads(result)
        except JSONDecodeError:
            # Errors other than iperf3 test errors
            logger.warning(
                f'Iperf check failed for "{self.related_object}", error - {result.strip()}'
            )
            return

        if mode == 'TCP':
            if exit_code != 0:
                logger.warning(
                    f'Iperf check failed for "{self.related_object}", {result["error"]}'
                )
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
                logger.warning(
                    f'Iperf check failed for "{self.related_object}", {result["error"]}'
                )
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
        Store result in the DB
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
        Creates iperf related charts
        """
        charts = [
            'bandwidth',
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
