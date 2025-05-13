import logging
import time

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from swapper import load_model

logger = logging.getLogger(__name__)

Check = load_model('check', 'Check')
Metric = load_model('monitoring', 'Metric')
Device = load_model('config', 'Device')


class BaseCheck(object):
    def __init__(self, check, params):
        self.check_instance = check
        self.related_object = check.content_object
        self.params = params

    @classmethod
    def get_related_metrics(cls):
        """
        Returns a tuple of metric names related to this check class.

        The default implementation returns a tuple containing the lowercase
        name of the class.

        Returns:
            tuple: A tuple of strings representing metric identifiers
        """
        return (cls.__name__.lower(),)

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

    @classmethod
    def may_execute(cls):
        """
        Class method that determines whether the check can be executed.

        Returns:
            bool: Always returns True by default.
                Subclasses may override this method to implement
                specific execution conditions.
        """
        return True

    def check(self, store=True):
        raise NotImplementedError

    def store(self, *args, **kwargs):
        raise NotImplementedError

    def timed_check(self, store=True):
        """
        Executes the check method and measures its execution time.

        Optionally stores the result and logs the time taken for the check execution
        and the time spent storing the result in the database(if available).

        Args:
            store (bool, optional): Whether to store the result of the check. Defaults to True.

        Returns:
            The result of the check method.

        Logs:
            The time taken to execute the check and store the result.
        """
        start_time = time.time()
        result = self.check(store=store)
        elapsed_time = time.time() - start_time
        if hasattr(self, '_store_result_elapsed_time'):
            elapsed_time -= self._store_result_elapsed_time
        logger.info(
            'Check "%s" executed in %.2fs, writing took %.2fs'
            % (
                self.check_instance,
                elapsed_time,
                getattr(self, '_store_result_elapsed_time', 0.0),
            ),
        )
        return result

    def timed_store(self, *args, **kwargs):
        """
        Calls the `store` method with the provided arguments and measures the time taken to execute it.

        The elapsed time (in seconds) is stored in the `timed_store` attribute of the instance.

        Args:
            *args: Variable length argument list to pass to the `store` method.
            **kwargs: Arbitrary keyword arguments to pass to the `store` method.

        Side Effects:
            Sets the `timed_store` attribute to the duration (in seconds) of the `store` method execution.
        """
        start_time = time.time()
        self.store(*args, **kwargs)
        self._store_result_elapsed_time = time.time() - start_time

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
