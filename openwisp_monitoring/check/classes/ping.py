import subprocess

from django.core.exceptions import ValidationError
from jsonschema import draft7_format_checker, validate
from jsonschema.exceptions import ValidationError as SchemaError
from swapper import load_model

from openwisp_utils.utils import deep_merge_dicts

from ... import settings as monitoring_settings
from .. import settings as app_settings
from ..exceptions import OperationalError
from .base import BaseCheck

Chart = load_model('monitoring', 'Chart')
Metric = load_model('monitoring', 'Metric')
AlertSettings = load_model('monitoring', 'AlertSettings')

DEFAULT_PING_CHECK_CONFIG = {
    'count': {
        'type': 'integer',
        'default': 5,
        'minimum': 2,
        # chosen to avoid slowing down the queue
        'maximum': 20,
    },
    'interval': {
        'type': 'integer',
        'default': 25,
        'minimum': 10,
        # chosen to avoid slowing down the queue
        'maximum': 1000,
    },
    'bytes': {'type': 'integer', 'default': 56, 'minimum': 12, 'maximum': 65508},
    'timeout': {
        'type': 'integer',
        'default': 800,
        'minimum': 5,
        # arbitrary chosen to avoid slowing down the queue
        'maximum': 1500,
    },
}


def get_ping_schema():
    schema = {
        '$schema': 'http://json-schema.org/draft-07/schema#',
        'type': 'object',
        'additionalProperties': False,
    }
    schema['properties'] = deep_merge_dicts(
        DEFAULT_PING_CHECK_CONFIG, app_settings.PING_CHECK_CONFIG
    )
    return schema


class Ping(BaseCheck):
    schema = get_ping_schema()

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
        count = self._get_param('count')
        interval = self._get_param('interval')
        bytes_ = self._get_param('bytes')
        timeout = self._get_param('timeout')
        ip = self._get_ip()
        #  if the device has no available IP
        if not ip:
            monitoring = self.related_object.monitoring
            # device not known yet, ignore
            if monitoring.status == 'unknown':
                return
            # device is known, simulate down
            result = {'reachable': 0, 'loss': 100.0}
            if store:
                self.store_result(result)
            return result
        command = [
            'fping',
            '-e',  # show elapsed (round-trip) time of packets
            '-c %s' % count,  # count of pings to send to each target,
            '-i %s' % interval,  # interval between sending pings(in ms)
            '-b %s' % bytes_,  # amount of ping data to send
            '-t %s' % timeout,  # individual target initial timeout (in ms)
            '-q',
            ip,
        ]
        stdout, stderr = self._command(command)
        # fpings shows statistics on stderr
        output = stderr.decode('utf8')
        try:
            parts = output.split('=')
            if len(parts) > 2:
                min, avg, max = parts[-1].strip().split('/')
                i = -2
            else:
                i = -1
            sent, received, loss = parts[i].strip().split(',')[0].split('/')
            loss = float(loss.strip('%'))
        except (IndexError, ValueError) as e:
            message = 'Unrecognized fping output:\n\n{0}'.format(output)
            raise OperationalError(message) from e
        result = {'reachable': int(loss < 100), 'loss': loss}
        if result['reachable']:
            result.update(
                {'rtt_min': float(min), 'rtt_avg': float(avg), 'rtt_max': float(max)}
            )
        if store:
            self.store_result(result)
        return result

    def store_result(self, result):
        """
        store result in the DB
        """
        metric = self._get_metric()
        copied = result.copy()
        reachable = copied.pop('reachable')
        metric.write(reachable, extra_values=copied)

    def _get_param(self, param):
        """
        Gets specified param or its default value according to the schema
        """
        return self.params.get(param, self.schema['properties'][param]['default'])

    def _get_ip(self):
        """
        Figures out ip to use or fails raising OperationalError
        """
        device = self.related_object
        ip = device.management_ip
        if not ip and not app_settings.MANAGEMENT_IP_ONLY:
            ip = device.last_ip
        return ip

    def _command(self, command):
        """
        Executes command (easier to mock)
        """
        p = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return p.stdout, p.stderr

    def _get_metric(self):
        """
        Gets or creates metric
        """
        metric, created = self._get_or_create_metric()
        if created:
            self._create_alert_settings(metric)
            self._create_charts(metric)
        return metric

    def _create_alert_settings(self, metric):
        alert_settings = AlertSettings(metric=metric)
        alert_settings.full_clean()
        alert_settings.save()

    def _create_charts(self, metric):
        """
        Creates device charts if necessary
        """
        charts = ['uptime', 'packet_loss', 'rtt']
        for chart in charts:
            if chart not in monitoring_settings.AUTO_CHARTS:
                continue
            chart = Chart(metric=metric, configuration=chart)
            chart.full_clean()
            chart.save()
