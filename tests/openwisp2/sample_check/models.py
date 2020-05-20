from django.db import models
from openwisp_monitoring.check.base.models import AbstractCheck
from swapper import swappable_setting


class DetailsModel(models.Model):
    details = models.CharField(max_length=64, blank=True, null=True)


class Check(AbstractCheck):
    class Meta(AbstractCheck.Meta):
        abstract = False
        swappable = swappable_setting('check', 'Check')
