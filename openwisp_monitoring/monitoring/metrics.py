from django.utils.translation import gettext_lazy as _

from openwisp_utils.utils import deep_merge_dicts

from . import settings as app_settings

DEFAULT_METRICS = {
    'ping': {
        'label': _('Ping'),
        'name': 'Ping',
        'key': 'ping',
        'field_name': 'reachable',
        'related_fields': ['loss', 'rtt_min', 'rtt_max', 'rtt_avg'],
    },
    'config_applied': {
        'label': _('Configuration Applied'),
        'name': 'Configuration Applied',
        'key': 'config_applied',
        'field_name': 'config_applied',
    },
    'traffic': {
        'label': _('Traffic'),
        'name': '{name}',
        'key': '{key}',
        'field_name': 'rx_bytes',
        'related_fields': ['tx_bytes'],
    },
    'clients': {
        'label': _('Clients'),
        'name': '{name}',
        'key': '{key}',
        'field_name': 'clients',
    },
    'disk': {
        'label': _('Disk usage'),
        'name': 'Disk usage',
        'key': 'disk',
        'field_name': 'used_disk',
    },
    'memory': {
        'label': _('Memory usage'),
        'name': 'Memory usage',
        'key': 'memory',
        'field_name': 'percent_used',
        'related_fields': [
            'total_memory',
            'free_memory',
            'buffered_memory',
            'shared_memory',
            'cached_memory',
            'available_memory',
        ],
    },
    'cpu': {
        'label': _('CPU usage'),
        'name': 'CPU usage',
        'key': 'cpu',
        'field_name': 'cpu_usage',
        'related_fields': ['load_1', 'load_5', 'load_15'],
    },
}


def get_metric_configuration():
    metrics = deep_merge_dicts(DEFAULT_METRICS, app_settings.ADDITIONAL_METRICS)
    # ensure configuration is not broken
    for options in metrics.values():
        assert 'label' in options
        assert 'name' in options
        assert 'key' in options
        assert 'field_name' in options
    return metrics


def get_metric_configuration_choices():
    metrics = get_metric_configuration()
    choices = []
    for key in sorted(metrics.keys()):
        label = metrics[key]['label']
        choices.append((key, label))
    return choices
