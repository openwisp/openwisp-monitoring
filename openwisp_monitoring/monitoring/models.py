from swapper import swappable_setting

from .base.models import AbstractAlertSettings, AbstractChart, AbstractMetric


class Metric(AbstractMetric):
    class Meta(AbstractMetric.Meta):
        abstract = False
        swappable = swappable_setting('monitoring', 'Metric')


class Chart(AbstractChart):
    class Meta(AbstractChart.Meta):
        abstract = False
        swappable = swappable_setting('monitoring', 'Chart')


class AlertSettings(AbstractAlertSettings):
    class Meta(AbstractAlertSettings.Meta):
        abstract = False
        swappable = swappable_setting('monitoring', 'AlertSettings')
