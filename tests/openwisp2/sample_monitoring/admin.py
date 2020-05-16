from django.contrib import admin
from openwisp_monitoring.monitoring.base.admin import (
    AbstracThresholdAdmin,
    AbstractMetricAdmin,
)
from swapper import load_model

Metric = load_model("sample_monitoring", "Metric")
Threshold = load_model("sample_monitoring", "Threshold")


@admin.register(Metric)
class MetricAdmin(AbstractMetricAdmin):
    pass


@admin.register(Threshold)
class ThresholdAdmin(AbstracThresholdAdmin):
    pass
