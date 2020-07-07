from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _
from openwisp_monitoring.db import chart_query

from openwisp_utils.utils import deep_merge_dicts

from . import settings as app_settings

DEFAULT_COLORS = [
    '#1f77b4',  # muted blue
    '#ff7f0e',  # safety orange
    '#2ca02c',  # cooked asparagus green
    '#d62728',  # brick red
    '#9467bd',  # muted purple
    '#8c564b',  # chestnut brown
    '#e377c2',  # raspberry yogurt pink
    '#7f7f7f',  # middle gray
    '#bcbd22',  # curry yellow-green
    '#17becf',  # blue-teal
]

DEFAULT_CHARTS = {
    'uptime': {
        'type': 'bar',
        'title': _('Uptime'),
        'description': _(
            'A value of 100% means reachable, 0% means unreachable, values in '
            'between 0% and 100% indicate the average reachability in the '
            'period observed. Obtained with the fping linux program.'
        ),
        'summary_labels': [_('Average uptime')],
        'unit': '%',
        'order': 200,
        'colorscale': {
            'max': 100,
            'min': 0,
            'label': _('Reachable'),
            'scale': [
                [0, '#c13000'],
                # [0.33, '#ef7d2d'],
                [0.5, '#deed0e'],
                [1, '#7db201'],
            ],
            'map': [
                [100, '#7db201', _('Reachable')],
                [33, '#deed0e', _('Partly reachable')],
                [None, '#c13000', _('Unreachable')],
            ],
            'fixed_value': 100,
        },
        'query': chart_query['uptime'],
    },
    'packet_loss': {
        'type': 'bar',
        'title': _('Packet loss'),
        'description': _(
            'Indicates the percentage of lost packets observed in ICMP probes. '
            'Obtained with the fping linux program.'
        ),
        'summary_labels': [_('Average packet loss')],
        'unit': '%',
        'colors': [DEFAULT_COLORS[3]],
        'order': 210,
        'query': chart_query['packet_loss'],
    },
    'rtt': {
        'type': 'scatter',
        'title': _('Round Trip Time'),
        'description': _(
            'Round trip time observed in ICMP probes, measuered in milliseconds.'
        ),
        'summary_labels': [
            _('Average RTT'),
            _('Average Max RTT'),
            _('Average Min RTT'),
        ],
        'unit': f' {_("ms")}',
        'order': 220,
        'query': chart_query['rtt'],
    },
    'wifi_clients': {
        'type': 'bar',
        'label': _('WiFi clients'),
        'title': _('WiFi clients: {metric.key}'),
        'description': _(
            'WiFi clients associated to the wireless interface "{metric.key}".'
        ),
        'summary_labels': [_('Total Unique WiFi clients')],
        'unit': '',
        'order': 230,
        'query': chart_query['wifi_clients'],
    },
    'traffic': {
        'type': 'scatter',
        'title': _('Traffic: {metric.key}'),
        'label': _('Traffic'),
        'description': _(
            'Network traffic, download and upload, measured on '
            'the interface "{metric.key}", measured in GB.'
        ),
        'summary_labels': [_('Total download traffic'), _('Total upload traffic')],
        'unit': f' {_("GB")}',
        'order': 240,
        'query': chart_query['traffic'],
    },
    'memory': {
        'type': 'scatter',
        'title': _('Memory Usage'),
        'description': _('Percentage of memory (RAM) being used.'),
        'summary_labels': [_('Memory Usage')],
        'unit': '%',
        'colors': [DEFAULT_COLORS[4]],
        'order': 250,
        'query': chart_query['memory'],
    },
    'cpu': {
        'type': 'scatter',
        'title': _('CPU Load'),
        'description': _(
            'Average CPU load, measured using the Linux load averages, '
            'taking into account the number of available CPUs.'
        ),
        'summary_labels': [_('CPU Load')],
        'unit': '%',
        'colors': [DEFAULT_COLORS[-3]],
        'order': 260,
        'query': chart_query['cpu'],
    },
    'disk': {
        'type': 'scatter',
        'title': _('Disk Usage'),
        'description': _(
            'Disk usage in percentage, calculated using all the available partitions.'
        ),
        'summary_labels': [_('Disk Usage')],
        'unit': '%',
        'colors': [DEFAULT_COLORS[-1]],
        'order': 270,
        'query': chart_query['disk'],
    },
}


def _validate_chart_configuration(chart_config):
    assert 'type' in chart_config
    assert 'title' in chart_config
    assert 'description' in chart_config
    assert 'order' in chart_config
    assert 'query' in chart_config
    if chart_config['query'] is None:
        assert 'unit' in chart_config
    if 'colorscale' in chart_config:
        assert 'max' in chart_config['colorscale']
        assert 'min' in chart_config['colorscale']
        assert 'label' in chart_config['colorscale']
        assert 'scale' in chart_config['colorscale']


def get_chart_configuration():
    charts = deep_merge_dicts(DEFAULT_CHARTS, app_settings.ADDITIONAL_CHARTS)
    # ensure configuration is not broken
    for key, options in charts.items():
        _validate_chart_configuration(options)
    return charts


def register_chart(chart_name, chart_config):
    """
    Registers a new chart configuration.
    """
    if not isinstance(chart_name, str):
        raise ImproperlyConfigured('Chart name should be type "str".')
    if not isinstance(chart_config, dict):
        raise ImproperlyConfigured('Chart configuration should be type "dict".')
    if chart_name in DEFAULT_CHARTS:
        raise ImproperlyConfigured(
            f'{chart_name} is an already registered Chart Configuration.'
        )

    _validate_chart_configuration(chart_config)
    DEFAULT_CHARTS.update({chart_name: chart_config})
    _register_chart_configuration_choice(chart_name, chart_config)


def unregister_chart(chart_name):
    if not isinstance(chart_name, str):
        raise ImproperlyConfigured('Chart configuration name should be type "str"')
    if chart_name not in DEFAULT_CHARTS:
        raise ImproperlyConfigured(f'No such Chart configuation "{chart_name}"')
    DEFAULT_CHARTS.pop(chart_name)
    _unregister_chart_configuration_choice(chart_name)


def _register_chart_configuration_choice(chart_name, chart_config):
    name = chart_config.get('verbose_name', chart_name)
    CHART_CONFIGURATION_CHOICES.append((chart_name, name))


def _unregister_chart_configuration_choice(chart_name):
    for index, (key, name) in enumerate(CHART_CONFIGURATION_CHOICES):
        if key == chart_name:
            CHART_CONFIGURATION_CHOICES.pop(index)
            return


def get_chart_configuration_choices():
    charts = get_chart_configuration()
    choices = []
    for key in sorted(charts.keys()):
        label = charts[key].get('label', charts[key]['title'])
        choices.append((key, label))
    return choices


CHART_CONFIGURATION_CHOICES = get_chart_configuration_choices()
