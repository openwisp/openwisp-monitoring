from django.dispatch import Signal

threshold_crossed = Signal(
    providing_args=['metric', 'alert_settings', 'target', 'first_time']
)
pre_metric_write = Signal(providing_args=['metric', 'values'])
post_metric_write = Signal(providing_args=['metric', 'values'])
