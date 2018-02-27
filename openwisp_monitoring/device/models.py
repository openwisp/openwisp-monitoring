import json

from django.core.exceptions import ValidationError
from jsonschema import validate
from jsonschema.exceptions import ValidationError as SchemaError

from openwisp_controller.config.models import Device

from ..monitoring.utils import query, write
from .schema import schema


class DeviceData(Device):
    schema = schema
    __data = None
    __key = 'device_data'

    class Meta:
        proxy = True

    def __init__(self, *args, **kwargs):
        self.data = kwargs.pop('data', None)
        return super(DeviceData, self).__init__(*args, **kwargs)

    @property
    def data(self):
        """
        retrieves last data snapshot from influxdb
        """
        if self.__data:
            return self.__data
        q = "SELECT data FROM {0} WHERE pk = '{1}' " \
            "ORDER BY time DESC LIMIT 1".format(self.__key, self.pk)
        points = list(query(q).get_points())
        if not points:
            return None
        return json.loads(points[0]['data'])

    @data.setter
    def data(self, data):
        """
        sets data
        """
        self.__data = data

    def validate_data(self):
        """
        validate data according to NetJSON DeviceMonitoring schema
        """
        try:
            validate(self.data, self.schema)
        except SchemaError as e:
            path = [str(el) for el in e.path]
            trigger = '/'.join(path)
            message = 'Invalid data in "#/{0}", '\
                      'validator says:\n\n{1}'.format(trigger, e.message)
            raise ValidationError(message)

    def save_data(self, time=None):
        """
        validates and saves data to influxdb
        """
        self.validate_data()
        write(name=self.__key,
              values={'data': self.json()},
              tags={'pk': self.pk},
              timestamp=time)

    def json(self, *args, **kwargs):
        return json.dumps(self.data, *args, **kwargs)
