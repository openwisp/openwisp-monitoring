from collections import OrderedDict

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.functional import cached_property
from django.utils.module_loading import import_string
from django.utils.translation import gettext_lazy as _
from jsonfield import JSONField

from openwisp_monitoring.check import settings as app_settings
from openwisp_monitoring.check.tasks import (
    auto_create_config_check,
    auto_create_iperf3_check,
    auto_create_ping,
)
from openwisp_utils.base import TimeStampedEditableModel

from ...utils import transaction_on_commit


class AbstractCheck(TimeStampedEditableModel):
    name = models.CharField(max_length=64, db_index=True)
    is_active = models.BooleanField(
        _('active'),
        default=True,
        db_index=True,
        help_text=_(
            'whether the check should be run, related metrics collected and alerts sent'
        ),
    )
    description = models.TextField(blank=True, help_text=_('Notes'))
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, null=True, blank=True
    )
    object_id = models.CharField(max_length=36, db_index=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    check_type = models.CharField(
        _('check type'),
        choices=app_settings.CHECK_CLASSES,
        db_index=True,
        max_length=128,
    )
    params = JSONField(
        _('parameters'),
        default=dict,
        blank=True,
        help_text=_('parameters needed to perform the check'),
        load_kwargs={'object_pairs_hook': OrderedDict},
        dump_kwargs={'indent': 4},
    )

    class Meta:
        abstract = True
        unique_together = ('name', 'object_id', 'content_type')

        permissions = (
            ('add_check_inline', 'Can add check inline'),
            ('change_check_inline', 'Can change check inline'),
            ('delete_check_inline', 'Can delete check inline'),
            ('view_check_inline', 'Can view check inline'),
        )

    def __str__(self):
        if not self.object_id or not self.content_type:
            return self.name
        obj = self.content_object
        model_name = obj.__class__.__name__
        return '{0} ({1}: {2})'.format(self.name, model_name, obj)

    def clean(self):
        self.check_instance.validate()

    def full_clean(self, *args, **kwargs):
        # The name of the check will be the same as the
        # 'check_type' chosen by the user when the
        # name field is empty (useful for CheckInline)
        if not self.name:
            self.name = self.get_check_type_display()
        return super().full_clean(*args, **kwargs)

    @cached_property
    def check_class(self):
        """
        returns check class
        """
        return import_string(self.check_type)

    @cached_property
    def check_instance(self):
        """
        returns check class instance
        """
        check_class = self.check_class
        return check_class(check=self, params=self.params)

    def perform_check(self, store=True):
        """
        initiates check instance and calls its check method
        """
        if (
            hasattr(self.content_object, 'organization_id')
            and self.content_object.organization.is_active is False
        ):
            return
        return self.check_instance.check(store=True)

    def perform_check_delayed(self, duration=0):
        from ..tasks import perform_check

        perform_check.apply_async(args=[self.id], countdown=duration)


def auto_ping_receiver(sender, instance, created, **kwargs):
    """
    Implements OPENWISP_MONITORING_AUTO_PING
    The creation step is executed in the background
    """
    # we need to skip this otherwise this task will be executed
    # every time the configuration is requested via checksum
    if not created:
        return
    transaction_on_commit(
        lambda: auto_create_ping.delay(
            model=sender.__name__.lower(),
            app_label=sender._meta.app_label,
            object_id=str(instance.pk),
        )
    )


def auto_config_check_receiver(sender, instance, created, **kwargs):
    """
    Implements OPENWISP_MONITORING_AUTO_DEVICE_CONFIG_CHECK
    The creation step is executed in the background
    """
    # we need to skip this otherwise this task will be executed
    # every time the configuration is requested via checksum
    if not created:
        return
    transaction_on_commit(
        lambda: auto_create_config_check.delay(
            model=sender.__name__.lower(),
            app_label=sender._meta.app_label,
            object_id=str(instance.pk),
        )
    )


def auto_iperf3_check_receiver(sender, instance, created, **kwargs):
    """
    Implements OPENWISP_MONITORING_AUTO_IPERF3
    The creation step is executed in the background
    """
    # we need to skip this otherwise this task will be executed
    # every time the configuration is requested via checksum
    if not created:
        return
    transaction_on_commit(
        lambda: auto_create_iperf3_check.delay(
            model=sender.__name__.lower(),
            app_label=sender._meta.app_label,
            object_id=str(instance.pk),
        )
    )
