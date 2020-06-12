from django.dispatch import Signal

alert_settings_crossed = Signal(providing_args=['metric', 'alert_settings', 'target'])
pre_metric_write = Signal(providing_args=['metric', 'values'])
post_metric_write = Signal(providing_args=['metric', 'values'])
