from django.db import models

from openwisp_monitoring.monitoring.base.models import (
    AbstractAlertSettings,
    AbstractChart,
    AbstractMetric,
)


class DetailsModel(models.Model):
    details = models.CharField(max_length=64, blank=True, null=True)

    class Meta:
        abstract = True


class Metric(DetailsModel, AbstractMetric):
    class Meta(AbstractMetric.Meta):
        abstract = False


class Chart(DetailsModel, AbstractChart):
    class Meta(AbstractChart.Meta):
        abstract = False


class AlertSettings(DetailsModel, AbstractAlertSettings):
    class Meta(AbstractAlertSettings.Meta):
        abstract = False
