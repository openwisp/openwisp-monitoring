import logging
from functools import reduce
from json import loads
from json.decoder import JSONDecodeError

from django.core.cache import cache
from django.core.exceptions import ValidationError
from jsonschema import draft7_format_checker, validate
from jsonschema.exceptions import ValidationError as SchemaError
from swapper import load_model

from openwisp_controller.connection.exceptions import NoWorkingDeviceConnectionError

from .. import settings as app_settings
from .base import BaseCheck

logger = logging.getLogger(__name__)

Chart = load_model('monitoring', 'Chart')
Metric = load_model('monitoring', 'Metric')
AlertSettings = load_model('monitoring', 'AlertSettings')
DeviceConnection = load_model('connection', 'DeviceConnection')

DEFAULT_IPERF3_CHECK_CONFIG = {
    'host': {
        'type': 'array',
        'items': {
            'type': 'string',
        },
        'default': [],
    },
    # username, password max_length chosen from iperf3 docs to avoid iperf3 param errors
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
                # sets the interval time in seconds
                # between periodic bandwidth, jitter, and loss reports
                'type': 'integer',
                'default': 10,
                'minimum': 1,
                # arbitrary chosen to avoid slowing down the queue (30min)
                'maximum': 1800,
            },
            'bytes': {
                # number of bytes to transmit (instead of 'time')
                'type': 'string',
                # default to '' since we're using time for
                # the test end condition instead of bytes
                'default': '',
            },
            'blockcount': {
                # number of blocks (packets) to transmit
                # instead of 'time' or 'bytes'
                'type': 'string',
                # default to '' since we're using time for
                # the test end condition instead of blockcount
                'default': '',
            },
            'window': {
                # window size / socket buffer size
                # this gets sent to the server and used on that side too
                'type': 'string',
                'default': '0',
            },
            'parallel': {
                # number of parallel client streams to run
                # note that iperf3 is single threaded
                # so if you are CPU bound this will not yield higher throughput
                'type': 'integer',
                'default': 1,
                # max, min parallel streams chosen from iperf3 docs
                'minimum': 1,
                'maximum': 128,
            },
            'reverse': {
                # reverse the direction of a test
                # the server sends data to the client
                'type': 'boolean',
                'default': False,
            },
            'bidirectional': {
                # test in both directions (normal and reverse)
                # with both the client and server sending
                # and receiving data simultaneously
                'type': 'boolean',
                'default': False,
            },
            'connect_timeout': {
                # set timeout for establishing the initial
                # control connection to the server, in milliseconds (ms)
                # providing a shorter value (ex. 1000 ms (1 sec)) may
                # speed up detection of a down iperf3 server
                'type': 'integer',
                'default': 1000,
                'minimum': 1,
                # arbitrary chosen to avoid slowing down the queue (1000 sec)
                'maximum': 1000000,
            },
            'tcp': {
                'type': 'object',
                'properties': {
                    'bitrate': {
                        # set target bitrate to n bits/sec
                        'type': 'string',
                        'default': '0',
                    },
                    'length': {
                        # length of buffer to read or write
                        'type': 'string',
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
                        # 30 Mbps
                        'default': '30M',
                    },
                    'length': {
                        # iperf3 tries to dynamically determine a
                        # reasonable sending size based on the path MTU
                        # if that cannot be determined it uses 1460 bytes
                        'type': 'string',
                        'default': '0',
                    },
                },
            },
        },
    },
}


def get_iperf3_schema():
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
    schema['properties'] = DEFAULT_IPERF3_CHECK_CONFIG
    return schema


class Iperf3(BaseCheck):
    schema = get_iperf3_schema()

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

    def _validate_iperf3_config(self, org):
        # if iperf3 config is present and validate it's params
        if app_settings.IPERF3_CHECK_CONFIG:
            self.validate_params(
                params=app_settings.IPERF3_CHECK_CONFIG.get(str(org.id))
            )

    def check(self, store=True):
        lock_acquired = False
        org = self.related_object.organization
        self._validate_iperf3_config(org)
        available_iperf3_servers = self._get_param('host', 'host.default')
        if not available_iperf3_servers:
            logger.warning(
                (
                    f'Iperf3 servers for organization "{org}" '
                    f'is not configured properly, iperf3 check skipped!'
                )
            )
            return
        # Avoid running the iperf3 check when the device monitoring status is "critical"
        if (
            self.related_object.monitoring
            and self.related_object.monitoring.status == 'critical'
        ):
            logger.info(
                (
                    f'"{self.related_object}" DeviceMonitoring '
                    'health status is "critical", iperf3 check skipped!'
                )
            )
            return
        time = self._get_param(
            'client_options.time', 'client_options.properties.time.default'
        )
        # Try to acquire a lock, or put task back on queue
        for server in available_iperf3_servers:
            server_lock_key = f'ow_monitoring_{org}_iperf3_check_{server}'
            # Set available_iperf3_server to the org device
            lock_acquired = cache.add(
                server_lock_key,
                str(self.related_object),
                timeout=app_settings.IPERF3_CHECK_LOCK_EXPIRE,
            )
            if lock_acquired:
                break
        else:
            logger.info(
                (
                    f'At the moment, all available iperf3 servers of organization "{org}" '
                    f'are busy running checks, putting "{self.check_instance}" back in the queue..'
                )
            )
            # Return the iperf3_check task to the queue,
            # it will executed after 2 * iperf3_check_time (TCP+UDP)
            self.check_instance.perform_check_delayed(duration=2 * time)
            return
        try:
            # Execute the iperf3 check with current available server
            result = self._run_iperf3_check(store, server, time)
        finally:
            # Release the lock after completion of the check
            cache.delete(server_lock_key)
            return result

    def _run_iperf3_check(self, store, server, time):
        try:
            device_connection = DeviceConnection.get_working_connection(
                self.related_object
            )
        except NoWorkingDeviceConnectionError:
            logger.warning(
                f'Failed to get a working DeviceConnection for "{self.related_object}", iperf3 check skipped!'
            )
            return
        command_tcp, command_udp = self._get_check_commands(server)

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

        result_tcp = self._get_iperf3_result(result, exit_code, mode='TCP')
        # UDP mode
        result, exit_code = device_connection.connector_instance.exec_command(
            command_udp, raise_unexpected_exit=False
        )
        result_udp = self._get_iperf3_result(result, exit_code, mode='UDP')
        result = {}
        if store and result_tcp and result_udp:
            # Store iperf3_result field 1 if any mode passes, store 0 when both fails
            iperf3_result = result_tcp['iperf3_result'] | result_udp['iperf3_result']
            result.update({**result_tcp, **result_udp, 'iperf3_result': iperf3_result})
            self.store_result(result)
        device_connection.disconnect()
        return result

    def _get_check_commands(self, server):
        """Returns tcp & udp commands for iperf3 check."""
        username = self._get_param('username', 'username.default')
        port = self._get_param(
            'client_options.port', 'client_options.properties.port.default'
        )
        window = self._get_param(
            'client_options.window', 'client_options.properties.window.default'
        )
        parallel = self._get_param(
            'client_options.parallel', 'client_options.properties.parallel.default'
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

        rev_or_bidir, test_end_condition = self._get_iperf3_test_conditions()
        logger.info(f'«« Iperf3 server : {server}, Device : {self.related_object} »»')
        command_tcp = (
            f'iperf3 -c {server} -p {port} {test_end_condition} --connect-timeout {ct} '
            f'-b {tcp_bitrate} -l {tcp_length} -w {window} -P {parallel} {rev_or_bidir} -J'
        )
        command_udp = (
            f'iperf3 -c {server} -p {port} {test_end_condition} --connect-timeout {ct} '
            f'-b {udp_bitrate} -l {udp_length} -w {window} -P {parallel} {rev_or_bidir} -u -J'
        )

        # All three parameters ie. username, password and rsa_public_key is required
        # for authentication to work, checking only username here
        if username:
            password = self._get_param('password', 'password.default')
            key = self._get_param('rsa_public_key', 'rsa_public_key.default')
            rsa_public_key = self._get_compelete_rsa_key(key)
            rsa_public_key_path = '/tmp/iperf3-public-key.pem'

            command_tcp = (
                f'echo "{rsa_public_key}" > {rsa_public_key_path} && '
                f'IPERF3_PASSWORD="{password}" iperf3 -c {server} -p {port} {test_end_condition} '
                f'--username "{username}" --rsa-public-key-path {rsa_public_key_path} --connect-timeout {ct} '
                f'-b {tcp_bitrate} -l {tcp_length} -w {window} -P {parallel} {rev_or_bidir} -J'
            )

            command_udp = (
                f'IPERF3_PASSWORD="{password}" iperf3 -c {server} -p {port} {test_end_condition} '
                f'--username "{username}" --rsa-public-key-path {rsa_public_key_path} --connect-timeout {ct} '
                f'-b {udp_bitrate} -l {udp_length} -w {window} -P {parallel} {rev_or_bidir} -u -J'
            )

            # If IPERF3_CHECK_DELETE_RSA_KEY, remove rsa_public_key from the device
            if app_settings.IPERF3_CHECK_DELETE_RSA_KEY:
                command_udp = f'{command_udp} && rm -f {rsa_public_key_path}'
        return command_tcp, command_udp

    def _get_iperf3_test_conditions(self):
        """Returns iperf3 check test conditions (rev_or_bidir, end_condition)."""
        time = self._get_param(
            'client_options.time', 'client_options.properties.time.default'
        )
        bytes = self._get_param(
            'client_options.bytes', 'client_options.properties.bytes.default'
        )
        blockcount = self._get_param(
            'client_options.blockcount', 'client_options.properties.blockcount.default'
        )
        reverse = self._get_param(
            'client_options.reverse', 'client_options.properties.reverse.default'
        )
        bidirectional = self._get_param(
            'client_options.bidirectional',
            'client_options.properties.bidirectional.default',
        )
        # by default we use 'time' param
        # for the iperf3 test end condition
        test_end_condition = f'-t {time}'
        # if 'bytes' present in config
        # use it instead of 'time'
        if bytes:
            test_end_condition = f'-n {bytes}'
        # if 'blockcount' present in config
        # use it instead of 'time' or 'bytes'
        if blockcount:
            test_end_condition = f'-k {blockcount}'
        # only one reverse condition can be use
        # reverse or bidirectional not both
        rev_or_bidir = ''
        if reverse:
            rev_or_bidir = '--reverse'
        if bidirectional:
            rev_or_bidir = '--bidir'
        return rev_or_bidir, test_end_condition

    def _get_compelete_rsa_key(self, key):
        """Returns RSA key with proper format."""
        pem_prefix = '-----BEGIN PUBLIC KEY-----\n'
        pem_suffix = '\n-----END PUBLIC KEY-----'
        key = key.strip()
        return f'{pem_prefix}{key}{pem_suffix}'

    def _deep_get(self, dictionary, keys, default=None):
        """Returns dict key value using dict and it's dot_key string,

        ie: key1.key2_nested.key3_nested, if found, otherwise returns
        default.
        """
        return reduce(
            lambda d, key: d.get(key, default) if isinstance(d, dict) else default,
            keys.split("."),
            dictionary,
        )

    def _get_param(self, conf_key, default_conf_key):
        """Returns specified param or its default value according to the schema."""
        org_id = str(self.related_object.organization.id)
        iperf3_config = app_settings.IPERF3_CHECK_CONFIG

        if self.params:
            check_params = self._deep_get(self.params, conf_key)
            if check_params:
                return check_params

        if iperf3_config:
            iperf3_config = iperf3_config.get(org_id)
            iperf3_config_param = self._deep_get(iperf3_config, conf_key)
            if iperf3_config_param:
                return iperf3_config_param

        return self._deep_get(DEFAULT_IPERF3_CHECK_CONFIG, default_conf_key)

    def _get_iperf3_result(self, result, exit_code, mode):
        """Returns iperf3 test result."""
        try:
            result = loads(result)
        except JSONDecodeError:
            # Errors other than iperf3 test errors
            logger.warning(
                f'Iperf3 check failed for "{self.related_object}", error - {result.strip()}'
            )
            return

        if mode == 'TCP':
            if exit_code != 0:
                logger.warning(
                    f'Iperf3 check failed for "{self.related_object}", {result["error"]}'
                )
                return {
                    'iperf3_result': 0,
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
                    'iperf3_result': 1,
                    'sent_bps_tcp': float(sent['bits_per_second']),
                    'received_bps_tcp': float(received['bits_per_second']),
                    'sent_bytes_tcp': sent['bytes'],
                    'received_bytes_tcp': received['bytes'],
                    'retransmits': sent['retransmits'],
                }

        elif mode == 'UDP':
            if exit_code != 0:
                logger.warning(
                    f'Iperf3 check failed for "{self.related_object}", {result["error"]}'
                )
                return {
                    'iperf3_result': 0,
                    'sent_bps_udp': 0.0,
                    'sent_bytes_udp': 0,
                    'jitter': 0.0,
                    'total_packets': 0,
                    'lost_packets': 0,
                    'lost_percent': 0.0,
                }
            else:
                return {
                    'iperf3_result': 1,
                    'sent_bps_udp': float(result['end']['sum']['bits_per_second']),
                    'sent_bytes_udp': result['end']['sum']['bytes'],
                    'jitter': float(result['end']['sum']['jitter_ms']),
                    'total_packets': result['end']['sum']['packets'],
                    'lost_packets': result['end']['sum']['lost_packets'],
                    'lost_percent': float(result['end']['sum']['lost_percent']),
                }

    def store_result(self, result):
        """Store result in the DB."""
        metric = self._get_metric()
        copied = result.copy()
        iperf3_result = copied.pop('iperf3_result')
        metric.write(iperf3_result, extra_values=copied)

    def _get_metric(self):
        """Gets or creates metric."""
        metric, created = self._get_or_create_metric()
        if created:
            self._create_alert_settings(metric)
            self._create_charts(metric)
        return metric

    def _create_alert_settings(self, metric):
        """Creates default iperf3 alert settings with is_active=False."""
        alert_settings = AlertSettings(metric=metric, is_active=False)
        alert_settings.full_clean()
        alert_settings.save()

    def _create_charts(self, metric):
        """Creates iperf3 related charts."""
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
