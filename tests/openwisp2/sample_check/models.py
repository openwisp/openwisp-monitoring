from django.db import models
from django.utils.timezone import now
from swapper import swappable_setting

from openwisp_monitoring.check.base.models import AbstractCheck


class Check(AbstractCheck):
    # This field has been added only for testing purposes
    last_called = models.DateTimeField(blank=True, null=True)

    class Meta(AbstractCheck.Meta):
        abstract = False
        swappable = swappable_setting('check', 'Check')

    def perform_check(self, store=True):
        """
        This method has been added for testing `last_called` field.
        It need not be added to retain original behaviour.
        """
        self.last_called = now()
        self.full_clean()
        self.save()
        return super().perform_check(store=store)
