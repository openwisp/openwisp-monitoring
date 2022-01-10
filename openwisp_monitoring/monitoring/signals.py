from django.dispatch import Signal

threshold_crossed = Signal()
threshold_crossed.__doc__ = """
Providing arguments: ['metric', 'alert_settings', 'target', 'first_time']
"""
pre_metric_write = Signal()
pre_metric_write.__doc__ = """
Providing arguments: ['metric', 'values', 'time', 'current']
"""
post_metric_write = Signal()
post_metric_write.__doc__ = """
Providing arguments: ['metric', 'values', 'time', 'current']
"""
