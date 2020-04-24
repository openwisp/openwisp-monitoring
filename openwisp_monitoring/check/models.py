from swapper import swappable_setting

from .base.models import AbstractCheck


class Check(AbstractCheck):
    class Meta(AbstractCheck.Meta):
        abstract = False
        swappable = swappable_setting('check', 'Check')
