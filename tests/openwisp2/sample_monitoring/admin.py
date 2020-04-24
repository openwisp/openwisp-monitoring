from django.contrib import admin
from openwisp_monitoring.monitoring.admin import MetricAdmin, ThresholdAdmin  # noqa

from .models import DetailsModel

admin.site.register(DetailsModel)
