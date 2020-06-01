from swapper import swappable_setting

from .base.models import AbstractAlertSettings, AbstractGraph, AbstractMetric


class Metric(AbstractMetric):
    class Meta(AbstractMetric.Meta):
        abstract = False
        swappable = swappable_setting('monitoring', 'Metric')


class Graph(AbstractGraph):
    class Meta(AbstractGraph.Meta):
        abstract = False
        swappable = swappable_setting('monitoring', 'Graph')


class AlertSettings(AbstractAlertSettings):
    class Meta(AbstractAlertSettings.Meta):
        abstract = False
        db_table = 'monitoring_alertsettings'
        swappable = swappable_setting('monitoring', 'AlertSettings')
