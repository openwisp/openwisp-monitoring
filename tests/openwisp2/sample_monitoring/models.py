from openwisp_monitoring.monitoring.base.models import (
    AbstractGraph,
    AbstractMetric,
    AbstractThreshold,
)


class Metric(AbstractMetric):
    def full_clean(self, *args, **kwargs):
        # clean up key before field validation
        self.key = self._makekey(self.key)
        return super(Metric, self).full_clean(*args, **kwargs)


class Graph(AbstractGraph):
    pass


class Threshold(AbstractThreshold):
    pass
