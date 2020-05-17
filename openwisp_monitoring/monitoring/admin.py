from django.contrib import admin
from swapper import load_model

from .base.admin import AbstracThresholdAdmin, AbstractMetricAdmin

Metric = load_model('monitoring', 'Metric')
Threshold = load_model('monitoring', 'Threshold')


@admin.register(Metric)
class MetricAdmin(AbstractMetricAdmin):
    model = Metric


@admin.register(Threshold)
class ThresholdAdmin(AbstracThresholdAdmin):
    model = Threshold
