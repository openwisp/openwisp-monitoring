from openwisp_monitoring.check.base.models import AbstractCheck
from swapper import swappable_setting


class Check(AbstractCheck):
    class Meta(AbstractCheck.Meta):
        abstract = False
        swappable = swappable_setting('check', 'Check')
