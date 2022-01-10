from django.dispatch import Signal

health_status_changed = Signal()
health_status_changed.__doc__ = """
Providing arguments: ['instance', 'status']
"""
device_metrics_received = Signal()
device_metrics_received.__doc__ = """
Providing arguments: ['instance', 'request', 'time', 'current']
"""
