from django.db import models
from openwisp_monitoring.monitoring.base.models import (
    AbstractGraph,
    AbstractMetric,
    AbstractThreshold,
)


class DetailsModel(models.Model):
    details = models.CharField(max_length=64, blank=True, null=True)


class Metric(AbstractMetric):
    pass


class Graph(AbstractGraph):
    pass


class Threshold(AbstractThreshold):
    pass
