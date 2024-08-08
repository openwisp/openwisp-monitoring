from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from swapper import load_model

Check = load_model('check', 'Check')
Metric = load_model('monitoring', 'Metric')
Device = load_model('config', 'Device')


class BaseCheck(object):
    def __init__(self, check, params):
        self.check_instance = check
        self.related_object = check.content_object
        self.params = params

    def validate_instance(self):
        # check instance is of type device
        obj = self.related_object
        if not obj or not isinstance(obj, Device):
            message = 'A related device is required to perform this operation'
            raise ValidationError({'content_type': message, 'object_id': message})

    def validate(self):
        self.validate_instance()
        self.validate_params()

    def validate_params(self):
        pass

    def check(self, store=True):
        raise NotImplementedError

    def _get_or_create_metric(self, configuration=None):
        """Gets or creates metric."""
        check = self.check_instance
        if check.object_id and check.content_type_id:
            obj_id = check.object_id
            ct = ContentType.objects.get_for_id(check.content_type_id)
        else:
            obj_id = str(check.id)
            ct = ContentType.objects.get_for_model(Check)
        options = dict(
            object_id=obj_id,
            content_type_id=ct.id,
            configuration=configuration or self.__class__.__name__.lower(),
        )
        metric, created = Metric._get_or_create(**options)
        return metric, created
