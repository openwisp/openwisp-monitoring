import subprocess

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from jsonschema import validate
from jsonschema.exceptions import ValidationError as SchemaError

from openwisp_controller.config.models import Device

from ..exceptions import OperationalError


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
                # arbitrary chosen to avoid slowing down the queue
                'maximum': 20
            },
            'interval': {
                'type': 'integer',
                'default': 25,
                'minimum': 10,
                # arbitrary chosen to avoid slowing down the queue
                'maximum': 1000
            },
            'bytes': {
                'type': 'integer',
                'default': 56,
                'minimum': 1,
                'maximum': 65508
            },
            'timeout': {
                'type': 'integer',
                'default': 500,
                'minimum': 5,
                # arbitrary chosen to avoid slowing down the queue
                'timeout': 1500
            }
        }
    }

    def __init__(self, check, params):
        self.instance = check.content_object
        self.params = params

    def validate(self):
        self.validate_instance()
        self.validate_params()

    def validate_instance(self):
        # check instance is of type device
        obj = self.instance
        if not obj or not isinstance(obj, Device):
            message = 'A related device is required ' \
                      'to perform this operation'
            raise ValidationError({'content_type': message,
                                   'object_id': message})

    def validate_params(self):
        try:
            validate(self.params, self.schema)
        except SchemaError as e:
            message = 'Invalid param'
            path = '/'.join(e.path)
            if path:
                message = '{0} in "{1}"'.format(message, path)
            message = '{0}: {1}'.format(message, e.message)
            raise ValidationError({'params': message})

    def check(self):
        count = self._get_param('count')
        interval = self._get_param('interval')
        bytes_ = self._get_param('bytes')
        timeout = self._get_param('timeout')
        ip = self._get_ip()
        command = [
            'fping',
            '-e',                # show elapsed (round-trip) time of packets
            '-c %s' % count,     # count of pings to send to each target,
            '-i %s' % interval,  # interval between sending pings(in ms)
            '-b %s' % bytes_,    # amount of ping data to send
            '-t %s' % timeout,   # individual target initial timeout (in ms)
            '-q',
            ip
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
            sent, received, loss = parts[i].strip() \
                                           .split(',')[0] \
                                           .split('/')
            loss = float(loss.strip('%'))
        except (IndexError, ValueError):
            message = 'Unrecognized fping output:\n\n{0}'.format(output)
            raise OperationalError(message)
        result = {
            'reachable': int(loss < 100),
            'loss': loss,
        }
        if result['reachable']:
            result.update({
                'rtt_min': float(min),
                'rtt_avg': float(avg),
                'rtt_max': float(max),
            })
        return result

    def _get_param(self, param):
        """
        Gets specified param or its default value according to the schema
        """
        return self.params.get(param, self.schema['properties'][param]['default'])

    def _get_ip(self):
        """
        Figures out ip to use or fails raising OperationalError
        """
        try:
            ip = self.instance.config.last_ip
            assert(ip is not None)
        except (ObjectDoesNotExist, AssertionError):
            raise OperationalError('Could not find a valid ip address')
        return ip

    def _command(self, command):
        """
        Executes command (easier to mock)
        """
        p = subprocess.Popen(command,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        return p.communicate()
