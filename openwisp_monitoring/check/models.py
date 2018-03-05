from collections import OrderedDict

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models.signals import post_save
from django.utils.encoding import python_2_unicode_compatible
from django.utils.functional import cached_property
from django.utils.module_loading import import_string
from django.utils.translation import ugettext_lazy as _
from jsonfield import JSONField

from openwisp_controller.config.models import Device
from openwisp_utils.base import TimeStampedEditableModel

from . import settings as app_settings


@python_2_unicode_compatible
class Check(TimeStampedEditableModel):
    name = models.CharField(max_length=64, db_index=True)
    active = models.BooleanField(default=True, db_index=True)
    description = models.TextField(blank=True, help_text=_('Notes'))
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE,
                                     null=True, blank=True)
    object_id = models.CharField(max_length=36, db_index=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    # TODO: relation to metric
    check = models.CharField(_('check type'),
                             choices=app_settings.CHECK_CLASSES,
                             db_index=True,
                             max_length=128,
                             help_text=_('Select check type'))
    params = JSONField(_('parameters'),
                       default=dict,
                       blank=True,
                       help_text=_('parameters needed to perform the check'),
                       load_kwargs={'object_pairs_hook': OrderedDict},
                       dump_kwargs={'indent': 4})

    class Meta:
        unique_together = ('name', 'object_id', 'content_type')

    def __str__(self):
        if not self.object_id or not self.content_type:
            return self.name
        obj = self.content_object
        model_name = obj.__class__.__name__
        return '{0} ({1}: {2})'.format(self.name, model_name, obj)

    def clean(self):
        self.check_instance.validate()

    @cached_property
    def check_class(self):
        """
        returns check class
        """
        return import_string(self.check)

    @cached_property
    def check_instance(self):
        """
        returns check class instance
        """
        check_class = self.check_class
        return check_class(check=self,
                           params=self.params)

    def perform_check(self, store=True):
        """
        initiates check instance and calls its check method
        """
        return self.check_instance.check(store=True)


if app_settings.AUTO_PING:
    from django.dispatch import receiver
    from .tasks import auto_create_ping

    @receiver(post_save, sender=Device, dispatch_uid='auto_ping')
    def auto_ping_receiver(sender, instance, created, **kwargs):
        """
        Implements OPENWISP_MONITORING_AUTO_PING
        The creation step is executed in the backround
        """
        auto_create_ping.delay(sender, instance, created, **kwargs)
