from swapper import swappable_setting

from .base.models import AbstractGraph, AbstractMetric, AbstractThreshold


class Metric(AbstractMetric):
    class Meta(AbstractMetric.Meta):
        abstract = False
        swappable = swappable_setting('monitoring', 'Metric')

    def full_clean(self, *args, **kwargs):
        # clean up key before field validation
        self.key = self._makekey(self.key)
        return super(Metric, self).full_clean(*args, **kwargs)


class Graph(AbstractGraph):
    class Meta(AbstractGraph.Meta):
        abstract = False
        swappable = swappable_setting('monitoring', 'Graph')


class Threshold(AbstractThreshold):
    class Meta(AbstractThreshold.Meta):
        abstract = False
        swappable = swappable_setting('monitoring', 'Threshold')
