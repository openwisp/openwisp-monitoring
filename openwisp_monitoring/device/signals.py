from django.dispatch import Signal

health_status_changed = Signal(providing_args=['instance', 'status'])
