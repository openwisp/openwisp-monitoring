from django.dispatch import Signal

health_status_changed = Signal(providing_args=['instance', 'status'])
device_metrics_received = Signal(providing_args=['instance', 'request'])
