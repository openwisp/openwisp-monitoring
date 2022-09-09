import logging
from functools import reduce
from json import loads
from json.decoder import JSONDecodeError

from django.core.cache import cache
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
                # between periodic bandwidth, jitter, and loss reports.
                'default': 10,
                'minimum': 1,
                # arbitrary chosen to avoid slowing down the queue (30min)
                'maximum': 1800,
            },
            'tcp': {
                'type': 'object',
                'properties': {
                    'bitrate': {
                        'type': 'string',
                        'default': '0',
                    }
                },
            },
            'udp': {
                'type': 'object',
                'properties': {
                    'bitrate': {
                        'type': 'string',
                        'default': '30M',
                    }
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

    def _validate_iperf_config(self, org):
        # if iperf config is present and validate it's params
        if app_settings.IPERF_CHECK_CONFIG:
            self.validate_params(params=app_settings.IPERF_CHECK_CONFIG[str(org.id)])

    def check(self, store=True):
        lock_acquired = False
        org = self.related_object.organization
        self._validate_iperf_config(org)
        available_iperf_servers = self._get_param('host', 'host.default')
        if not available_iperf_servers:
            logger.warning(
                (
                    f'Iperf servers for organization "{org}" '
                    f'is not configured properly, iperf check skipped!'
                )
            )
            return
        time = self._get_param(
            'client_options.time', 'client_options.properties.time.default'
        )
        # Try to acquire a lock, or put task back on queue
        for server in available_iperf_servers:
            server_lock_key = f'ow_monitoring_{org}_iperf_check_{server}'
            # Set available_iperf_server to the org device
            lock_acquired = cache.add(
                server_lock_key,
                str(self.related_object),
                timeout=app_settings.IPERF_CHECK_LOCK_EXPIRE,
            )
            if lock_acquired:
                break
        else:
            logger.warning(
                (
                    f'At the moment, all available iperf servers of organization "{org}" '
                    f'are busy running checks, putting "{self.check_instance}" back in the queue..'
                )
            )
            # Return the iperf_check task to the queue,
            # it will executed after 2 * iperf_check_time (TCP+UDP)
            self.check_instance.perform_check_delayed(duration=2 * time)
            return
        try:
            # Execute the iperf check with current available server
            result = self._run_iperf_check(store, server, time)
        finally:
            # Release the lock after completion of the check
            cache.delete(server_lock_key)
            return result

    def _run_iperf_check(self, store, server, time):
        port = self._get_param(
            'client_options.port', 'client_options.properties.port.default'
        )
        tcp_bitrate = self._get_param(
            'client_options.tcp.bitrate',
            'client_options.properties.tcp.properties.bitrate.default',
        )
        udp_bitrate = self._get_param(
            'client_options.udp.bitrate',
            'client_options.properties.udp.properties.bitrate.default',
        )
        username = self._get_param('username', 'username.default')
        device_connection = self._get_device_connection()
        if not device_connection:
            logger.warning(
                f'Failed to get a working DeviceConnection for "{self.related_object}", iperf check skipped!'
            )
            return
        # The DeviceConnection could fail if the management tunnel is down.
        if not device_connection.connect():
            logger.warning(
                f'DeviceConnection for "{self.related_object}" is not working, iperf check skipped!'
            )
            return

        logger.info(f'«« Iperf server : {server}, Device : {self.related_object} »»')
        command_tcp = f'iperf3 -c {server} -p {port} -t {time} -b {tcp_bitrate} -J'
        command_udp = f'iperf3 -c {server} -p {port} -t {time} -b {udp_bitrate} -u -J'

        # All three parameters ie. username, password and rsa_public_key is required
        # for authentication to work, checking only username here
        if username:
            password = self._get_param('password', 'password.default')
            key = self._get_param('rsa_public_key', 'rsa_public_key.default')
            rsa_public_key = self._get_compelete_rsa_key(key)
            rsa_public_key_path = '/tmp/iperf-public-key.pem'

            command_tcp = f'echo "{rsa_public_key}" > {rsa_public_key_path} && \
            IPERF3_PASSWORD="{password}" iperf3 -c {server} -p {port} -t {time} \
            --username "{username}" --rsa-public-key-path {rsa_public_key_path} -b {tcp_bitrate} -J'

            command_udp = f'echo "{rsa_public_key}" > {rsa_public_key_path} && \
            IPERF3_PASSWORD="{password}" iperf3 -c {server} -p {port} -t {time} \
            --username "{username}" --rsa-public-key-path {rsa_public_key_path} -b {udp_bitrate} -u -J'
            # If IPERF_CHECK_DELETE_RSA_KEY, remove rsa_public_key from the device
            if app_settings.IPERF_CHECK_DELETE_RSA_KEY:
                command_udp = f'{command_udp} && rm -f {rsa_public_key_path}'

        # TCP mode
        result, exit_code = device_connection.connector_instance.exec_command(
            command_tcp, raise_unexpected_exit=False
        )
        # Exit code 127 : command doesn't exist
        if exit_code == 127:
            logger.warning(
                f'Iperf3 is not installed on the "{self.related_object}", error - {result.strip()}'
            )
            return

        result_tcp = self._get_iperf_result(result, exit_code, mode='TCP')
        # UDP mode
        result, exit_code = device_connection.connector_instance.exec_command(
            command_udp, raise_unexpected_exit=False
        )
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
