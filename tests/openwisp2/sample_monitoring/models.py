from django.db import models
from openwisp_monitoring.monitoring.base.models import (
    AbstractGraph,
    AbstractMetric,
    AbstractThreshold,
)


class DetailsModel(models.Model):
    details = models.CharField(max_length=64, blank=True, null=True)

    class Meta:
        abstract = True


class Metric(DetailsModel, AbstractMetric):
    class Meta(AbstractMetric.Meta):
        abstract = False


class Graph(DetailsModel, AbstractGraph):
    class Meta(AbstractGraph.Meta):
        abstract = False


class Threshold(DetailsModel, AbstractThreshold):
    class Meta(AbstractThreshold.Meta):
        abstract = False
