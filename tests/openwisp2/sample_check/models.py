from django.db import models
from django.utils.timezone import now
from openwisp_monitoring.check.base.models import AbstractCheck
from swapper import swappable_setting


class Check(AbstractCheck):
    last_called = models.DateTimeField(blank=True, null=True)

    class Meta(AbstractCheck.Meta):
        abstract = False
        swappable = swappable_setting('check', 'Check')

    def perform_check(self, store=True):
        """
        initiates check instance and calls its check method
        """
        self.last_called = now()
        self.full_clean()
        self.save()
        return self.check_instance.check(store=True)
