import json
import collections
from copy import deepcopy

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import ugettext_lazy as _
from jsonfield import JSONField

from openwisp_utils.base import TimeStampedEditableModel

from jsonschema import validate
from jsonschema.exceptions import ValidationError as SchemaError

from .schema import schema


class DeviceDynamicData(TimeStampedEditableModel):
    """
    stores device information that changes over time
    this information will be either received or retrieved
    from the network device itself
    """
    device = models.OneToOneField('config.Device',
                                  on_delete=models.CASCADE,
                                  related_name='dynamic_data')
    data = JSONField(_('data'),
                     default=dict,
                     help_text=_('dynamic device data in NetJSON DeviceMonitoring format'),
                     load_kwargs={'object_pairs_hook': collections.OrderedDict},
                     dump_kwargs={'indent': 4})
    schema = schema

    def clean(self):
        """
        validate data field according
        to NetJSON DeviceMonitoring schema
        """
        try:
            validate(self._netjson, self.schema)
        except SchemaError as e:
            path = [str(el) for el in e.path]
            trigger = '/'.join(path)
            message = 'Invalid data in "#/{0}", '\
                      'validator says:\n\n{1}'.format(trigger, e.message)
            raise ValidationError({'data': message})

    @property
    def _netjson(self):
        data = deepcopy(self.data)
        data.update({'type': 'DeviceMonitoring'})
        return data

    def json(self, *args, **kwargs):
        return json.dumps(self._netjson, *args, **kwargs)
