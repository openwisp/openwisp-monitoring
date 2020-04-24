from django.contrib import admin

from .base.admin import AbstracThresholdAdmin, AbstractMetricAdmin
from .models import Metric, Threshold


@admin.register(Metric)
class MetricAdmin(AbstractMetricAdmin):
    model = Metric


@admin.register(Threshold)
class ThresholdAdmin(AbstracThresholdAdmin):
    model = Threshold
