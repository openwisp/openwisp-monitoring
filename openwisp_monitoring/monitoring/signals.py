from django.dispatch import Signal

threshold_crossed = Signal(providing_args=['metric', 'threshold', 'target'])
