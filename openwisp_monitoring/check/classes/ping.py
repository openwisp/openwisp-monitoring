import subprocess

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from jsonschema import draft7_format_checker, validate
from jsonschema.exceptions import ValidationError as SchemaError
from swapper import load_model

from openwisp_controller.config.models import Device

from ... import settings as monitoring_settings
from .. import settings as app_settings
from ..exceptions import OperationalError

Graph = load_model('monitoring', 'Graph')
Metric = load_model('monitoring', 'Metric')
Threshold = load_model('monitoring', 'Threshold')


class Ping(object):
    schema = {
        '$schema': 'http://json-schema.org/draft-04/schema#',
        'type': 'object',
        'additionalProperties': False,
        'properties': {
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
            'bytes': {'type': 'integer', 'default': 56, 'minimum': 1, 'maximum': 65508},
            'timeout': {
                'type': 'integer',
                'default': 800,
                'minimum': 5,
                # arbitrary chosen to avoid slowing down the queue
                'maximum': 1500,
            },
        },
    }

    def __init__(self, check, params):
        self.check_instance = check
        self.related_object = check.content_object
        self.params = params

    def validate(self):
        self.validate_instance()
        self.validate_params()

    def validate_instance(self):
        # check instance is of type device
        obj = self.related_object
        if not obj or not isinstance(obj, Device):
            message = 'A related device is required ' 'to perform this operation'
            raise ValidationError({'content_type': message, 'object_id': message})

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
        result = {
            'reachable': int(loss < 100),
            'loss': loss,
        }
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
        p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return p.communicate()

    def _get_metric(self):
        """
        Gets or creates metric
        """
        check = self.check_instance
        if check.object_id and check.content_type:
            obj_id = check.object_id
            ct = check.content_type
        else:
            obj_id = str(check.id)
            ct = ContentType.objects.get(
                app_label=check._meta.app_label, model=check.__class__.__name__.lower()
            )
        options = dict(
            name=check.name,
            object_id=obj_id,
            content_type=ct,
            field_name='reachable',
            key=self.__class__.__name__.lower(),
        )
        metric, created = Metric.objects.get_or_create(**options)
        if created:
            self._create_threshold(metric)
            self._create_graphs(metric)
        return metric

    def _create_threshold(self, metric):
        t = Threshold(metric=metric, operator='<', value=1, seconds=0)
        t.full_clean()
        t.save()

    def _create_graphs(self, metric):
        """
        Creates device graphs if necessary
        """
        graphs = ['uptime', 'packet_loss', 'rtt']
        for graph in graphs:
            if graph not in monitoring_settings.AUTO_GRAPHS:
                continue
            graph = Graph(metric=metric, configuration=graph)
            graph.full_clean()
            graph.save()
