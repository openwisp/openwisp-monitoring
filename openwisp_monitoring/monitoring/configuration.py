from collections import OrderedDict
from copy import deepcopy

from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _
from openwisp_notifications.types import (
    register_notification_type,
    unregister_notification_type,
)

from openwisp_monitoring.db import chart_query
from openwisp_monitoring.monitoring.utils import clean_timeseries_data_key
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

ACCESS_TECHNOLOGIES = OrderedDict(
    (
        ('gsm', '#b42a0c'),
        ('cdma1x', '#dd5817'),
        ('evdo', '#df7514'),
        ('umts', '#efdd50'),
        ('lte', '#67c368'),
        ('5g', '#377873'),
    )
)


def _get_access_tech():
    res = []
    keys_list = list(ACCESS_TECHNOLOGIES.keys())
    for i in reversed(keys_list):
        res.append([keys_list.index(i), ACCESS_TECHNOLOGIES[i], i])
    return res


# under discussion
DEFAULT_METRICS = {
    'ping': {
        'label': _('Ping'),
        'name': 'Ping',
        'key': 'ping',
        'field_name': 'reachable',
        'related_fields': ['loss', 'rtt_min', 'rtt_max', 'rtt_avg'],
        'charts': {
            'uptime': {
                'type': 'bar',
                'title': _('Ping Success Rate'),
                'description': _(
                    'A value of 100% means reachable, 0% means unreachable, values in '
                    'between 0% and 100% indicate the average reachability in the '
                    'period observed. Obtained with the fping linux program.'
                ),
                'summary_labels': [_('Average Ping Success Rate')],
                'unit': '%',
                'order': 200,
                'colorscale': {
                    'max': 100,
                    'min': 0,
                    'label': _('Rate'),
                    'scale': [
                        [0, '#c13000'],
                        [0.1, '#ec7204'],
                        [0.5, '#deed0e'],
                        [0.9, '#90d000'],
                        [1, '#7db201'],
                    ],
                    'map': [
                        [100, '#7db201', _('Flawless')],
                        [90, '#90d000', _('Mostly Reachable')],
                        [50, '#deed0e', _('Partly Reachable')],
                        [10, '#ec7204', _('Mostly Unreachable')],
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
                'unit': _(' ms'),
                'order': 220,
                'query': chart_query['rtt'],
            },
        },
        'alert_settings': {'operator': '<', 'threshold': 1, 'tolerance': 0},
        'notification': {
            'problem': {
                'verbose_name': 'Ping PROBLEM',
                'verb': _('is not reachable'),
                'level': 'warning',
                'email_subject': _(
                    '[{site.name}] PROBLEM: {notification.target} {notification.verb}'
                ),
                'message': _(
                    'The device [{notification.target}]({notification.target_link}) '
                    '{notification.verb}.'
                ),
            },
            'recovery': {
                'verbose_name': 'Ping RECOVERY',
                'verb': _('is reachable again'),
                'level': 'info',
                'email_subject': _(
                    '[{site.name}] RECOVERY: {notification.target} {notification.verb}'
                ),
                'message': _(
                    'The device [{notification.target}]({notification.target_link}) '
                    '{notification.verb}.'
                ),
            },
        },
    },
    'config_applied': {
        'label': _('Configuration Applied'),
        'name': 'Configuration Applied',
        'key': 'config_applied',
        'field_name': 'config_applied',
        'alert_settings': {'operator': '<', 'threshold': 1, 'tolerance': 5},
        'notification': {
            'problem': {
                'verbose_name': 'Configuration Applied PROBLEM',
                'verb': _('has not been applied'),
                'level': 'warning',
                'email_subject': _(
                    '[{site.name}] PROBLEM: {notification.target} configuration '
                    'status issue'
                ),
                'message': _(
                    'The configuration of device [{notification.target}]'
                    '({notification.target_link}) {notification.verb} in a timely manner.'
                ),
            },
            'recovery': {
                'verbose_name': 'Configuration Applied RECOVERY',
                'verb': _('configuration has been applied again'),
                'level': 'info',
                'email_subject': _(
                    '[{site.name}] RECOVERY: {notification.target} {notification.verb} '
                    'successfully'
                ),
                'message': _(
                    'The configuration of device [{notification.target}]({notification.target_link}) '
                    '{notification.verb} successfully.'
                ),
            },
        },
    },
    'traffic': {
        'label': _('Traffic'),
        'name': '{name}',
        'key': '{key}',
        'field_name': 'rx_bytes',
        'related_fields': ['tx_bytes'],
        'charts': {
            'traffic': {
                'type': 'stackedbar+lines',
                'calculate_total': True,
                'trace_type': {
                    'download': 'stackedbar',
                    'upload': 'stackedbar',
                    'total': 'lines',
                },
                'trace_order': ['total', 'download', 'upload'],
                'title': _('Traffic: {ifname}'),
                'label': _('Traffic'),
                'description': _(
                    'Network traffic (total, download and upload) '
                    'of the interface "{ifname}".'
                ),
                'summary_labels': [
                    _('Total traffic'),
                    _('Total download traffic'),
                    _('Total upload traffic'),
                ],
                'unit': 'adaptive_prefix+B',
                'order': 240,
                'query': chart_query['traffic'],
                'colors': [
                    DEFAULT_COLORS[7],
                    DEFAULT_COLORS[0],
                    DEFAULT_COLORS[1],
                ],
            }
        },
    },
    'general_traffic': {
        'label': _('General Traffic'),
        'name': 'General Traffic',
        'key': 'traffic',
        'field_name': 'rx_bytes',
        'related_fields': ['tx_bytes'],
        'charts': {
            'general_traffic': {
                'type': 'stackedbar+lines',
                'calculate_total': True,
                'fill': 'none',
                'trace_type': {
                    'download': 'stackedbar',
                    'upload': 'stackedbar',
                    'total': 'lines',
                },
                'trace_order': ['total', 'download', 'upload'],
                'title': _('General Traffic'),
                'label': _('General Traffic'),
                'description': _(
                    'Network traffic of the whole network (total, download, upload).'
                ),
                'summary_labels': [
                    _('Total traffic'),
                    _('Total download traffic'),
                    _('Total upload traffic'),
                ],
                'unit': 'adaptive_prefix+B',
                'order': 240,
                'query': chart_query['general_traffic'],
                'query_default_param': {
                    'organization_id': '',
                    'ifname': '',
                    'location_id': '',
                    'floorplan_id': '',
                },
                'colors': [
                    DEFAULT_COLORS[7],
                    DEFAULT_COLORS[0],
                    DEFAULT_COLORS[1],
                ],
            }
        },
    },
    'clients': {
        'label': _('Clients'),
        'name': '{name}',
        'key': '{key}',
        'field_name': 'clients',
        'charts': {
            'wifi_clients': {
                'type': 'bar',
                'label': _('WiFi clients'),
                'title': _('WiFi clients: {ifname}'),
                'description': _(
                    'WiFi clients associated to the wireless interface "{ifname}".'
                ),
                'summary_labels': [_('Total Unique WiFi clients')],
                'unit': '',
                'order': 230,
                'query': chart_query['wifi_clients'],
            }
        },
    },
    'general_clients': {
        'label': _('General WiFi Clients'),
        'name': _('General WiFi Clients'),
        'key': 'wifi_clients',
        'field_name': 'clients',
        'charts': {
            'gen_wifi_clients': {
                'type': 'bar',
                'label': _('General WiFi Clients'),
                'title': _('General WiFi Clients'),
                'description': _('Unique WiFi clients count of the entire network.'),
                'summary_labels': [_('Total Unique WiFi clients')],
                'unit': '',
                'order': 230,
                'query': chart_query['general_wifi_clients'],
                'query_default_param': {
                    'organization_id': '',
                    'location_id': '',
                    'floorplan_id': '',
                },
            }
        },
    },
    'disk': {
        'label': _('Disk usage'),
        'name': 'Disk usage',
        'key': 'disk',
        'field_name': 'used_disk',
        'charts': {
            'disk': {
                'type': 'scatter',
                'title': _('Disk Usage'),
                'description': _(
                    'Disk usage in percentage, calculated using all the available partitions.'
                ),
                'summary_labels': [_('Disk Usage')],
                'unit': '%',
                'colors': [DEFAULT_COLORS[9]],
                'order': 270,
                'query': chart_query['disk'],
            }
        },
        'alert_settings': {'operator': '>', 'threshold': 90, 'tolerance': 0},
        'notification': {
            'problem': {
                'verbose_name': 'Disk usage PROBLEM',
                'verb': _('is experiencing a peak in'),
                'level': 'warning',
                'email_subject': _(
                    '[{site.name}] PROBLEM: {notification.target} {notification.verb} disk usage'
                ),
                'message': _(
                    'The device [{notification.target}]({notification.target_link}) '
                    '{notification.verb} disk usage which has gone over '
                    '{notification.actor.alertsettings.threshold}%.'
                ),
            },
            'recovery': {
                'verbose_name': 'Disk usage RECOVERY',
                'verb': _('has returned to normal levels'),
                'level': 'info',
                'email_subject': _(
                    '[{site.name}] RECOVERY: {notification.target} disk usage '
                    '{notification.verb}'
                ),
                'message': (
                    'The device [{notification.target}]({notification.target_link}) '
                    'disk usage {notification.verb}.'
                ),
            },
        },
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
        'charts': {
            'memory': {
                'type': 'scatter',
                'title': _('Memory Usage'),
                'description': _('Percentage of memory (RAM) being used.'),
                'summary_labels': [_('Memory Usage')],
                'unit': '%',
                'colors': [DEFAULT_COLORS[4]],
                'order': 250,
                'query': chart_query['memory'],
            }
        },
        'alert_settings': {'operator': '>', 'threshold': 95, 'tolerance': 5},
        'notification': {
            'problem': {
                'verbose_name': 'Memory usage PROBLEM',
                'verb': _('is experiencing a peak in'),
                'level': 'warning',
                'email_subject': _(
                    '[{site.name}] PROBLEM: {notification.target} {notification.verb} RAM usage'
                ),
                'message': _(
                    'The device [{notification.target}]({notification.target_link}) '
                    '{notification.verb} RAM usage which has gone '
                    'over {notification.actor.alertsettings.threshold}%.'
                ),
            },
            'recovery': {
                'verbose_name': 'Memory usage RECOVERY',
                'verb': _('has returned to normal levels'),
                'level': 'info',
                'email_subject': _(
                    '[{site.name}] RECOVERY: {notification.target} RAM usage {notification.verb}'
                ),
                'message': (
                    'The device [{notification.target}]({notification.target_link}) RAM usage '
                    '{notification.verb}.'
                ),
            },
        },
    },
    'cpu': {
        'label': _('CPU usage'),
        'name': 'CPU usage',
        'key': 'cpu',
        'field_name': 'cpu_usage',
        'related_fields': ['load_1', 'load_5', 'load_15'],
        'charts': {
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
            }
        },
        'alert_settings': {'operator': '>', 'threshold': 90, 'tolerance': 5},
        'notification': {
            'problem': {
                'verbose_name': 'CPU usage PROBLEM',
                'verb': _('is experiencing a peak in'),
                'level': 'warning',
                'email_subject': _(
                    '[{site.name}] PROBLEM: {notification.target} {notification.verb} CPU usage'
                ),
                'message': _(
                    'The device [{notification.target}]({notification.target_link}) '
                    '{notification.verb} CPU usage which has gone '
                    'over {notification.actor.alertsettings.threshold}%.'
                ),
            },
            'recovery': {
                'verbose_name': 'CPU usage RECOVERY',
                'verb': _('has returned to normal levels'),
                'level': 'info',
                'email_subject': _(
                    '[{site.name}] RECOVERY: {notification.target} CPU usage {notification.verb}'
                ),
                'message': (
                    'The device [{notification.target}]({notification.target_link}) '
                    'CPU usage {notification.verb}.'
                ),
            },
        },
    },
    # modem-manager charts
    'signal_strength': {
        'label': _('Signal Strength'),
        'name': '{name}',
        'key': '{key}',
        'field_name': 'signal_strength',
        'related_fields': ['signal_power'],
        'charts': {
            'signal_strength': {
                'type': 'scatter',
                'fill': 'none',
                'yaxis': {'zeroline': False},
                'title': _('Signal Strength'),
                'colors': (DEFAULT_COLORS[3], DEFAULT_COLORS[0]),
                'description': _('Signal Strength and Signal Power, measured in dBm.'),
                'summary_labels': [
                    _('Average Signal Power'),
                    _('Average Signal Strength'),
                ],
                'unit': _(' dBm'),
                'order': 205,
                'query': chart_query['signal_strength'],
            }
        },
    },
    'signal_quality': {
        'label': _('Signal Quality'),
        'name': '{name}',
        'key': '{key}',
        'field_name': 'signal_quality',
        'related_fields': ['snr'],
        'charts': {
            'signal_quality': {
                'type': 'scatter',
                'fill': 'none',
                'yaxis': {'zeroline': False},
                'title': _('Signal Quality'),
                'colors': (DEFAULT_COLORS[3], DEFAULT_COLORS[0]),
                'description': _(
                    _('Signal Quality and Signal to Noise Ratio (SNR), measured in dB.')
                ),
                'summary_labels': [
                    _('Average Signal Quality'),
                    _('Average Signal to Noise Ratio'),
                ],
                'unit': _(' dB'),
                'order': 206,
                'query': chart_query['signal_quality'],
            }
        },
    },
    'access_tech': {
        'label': _('Access Technology'),
        'name': '{name}',
        'key': '{key}',
        'field_name': 'access_tech',
        'charts': {
            'access_tech': {
                'type': 'bar',
                'title': _('Access Technology'),
                'description': _(
                    _(
                        'Shows the access technology (LTE, UTMS, CDMA1x, etc.) '
                        'in use on the device at the specified time.'
                    )
                ),
                'order': 207,
                'unit': '',
                'colorscale': {
                    'label': '',
                    'map': _get_access_tech(),
                    'max': 5,
                    'min': 0,
                    'scale': (
                        (0, '#b42a0c'),
                        (0.1, '#dd5817'),
                        (0.2, '#df7514'),
                        (0.5, '#efdd50'),
                        (0.8, '#67c368'),
                        (1, '#377873'),
                    ),
                    'fixed_value': 100,
                },
                'query': chart_query['access_tech'],
            }
        },
    },
    'iperf3': {
        'label': _('Iperf3'),
        'name': 'Iperf3',
        'key': 'iperf3',
        'field_name': 'iperf3_result',
        'related_fields': [
            'sent_bps_tcp',
            'received_bps_tcp',
            'sent_bytes_tcp',
            'received_bytes_tcp',
            'retransmits',
            'sent_bytes_udp',
            'sent_bps_udp',
            'jitter',
            'total_packets',
            'lost_packets',
            'lost_percent',
        ],
        'charts': {
            'bandwidth': {
                'type': 'scatter',
                'connect_points': True,
                'title': _('Bandwidth'),
                'fill': 'none',
                'description': _('Bitrate during Iperf3 test.'),
                'summary_labels': [
                    _('TCP bitrate'),
                    _('UDP bitrate'),
                ],
                'unit': 'adaptive_prefix+bps',
                'order': 280,
                'query': chart_query['bandwidth'],
                'colors': [
                    DEFAULT_COLORS[0],
                    DEFAULT_COLORS[3],
                ],
            },
            'transfer': {
                'type': 'scatter',
                'connect_points': True,
                'fill': 'none',
                'title': _('Transferred Data'),
                'description': _('Transferred Data during Iperf3 test.'),
                'summary_labels': [
                    _('TCP transferred data'),
                    _('UDP transferred data'),
                ],
                'unit': 'adaptive_prefix+B',
                'order': 290,
                'query': chart_query['transfer'],
                'colors': [
                    DEFAULT_COLORS[0],
                    DEFAULT_COLORS[3],
                ],
            },
            'retransmits': {
                'type': 'scatter',
                'connect_points': True,
                'title': _('Retransmits'),
                'description': _('Retransmits during Iperf3 test in TCP mode.'),
                'summary_labels': [_('Restransmits')],
                'unit': '',
                'order': 300,
                'query': chart_query['retransmits'],
                'colors': [DEFAULT_COLORS[-3]],
            },
            'jitter': {
                'type': 'scatter',
                'connect_points': True,
                'title': _('Jitter'),
                'description': _(
                    'Jitter is a variance in latency measured using Iperf3 utility in UDP mode.'
                ),
                'summary_labels': [
                    _('Jitter'),
                ],
                'unit': _(' ms'),
                'order': 330,
                'query': chart_query['jitter'],
                'colors': [DEFAULT_COLORS[4]],
            },
            'datagram': {
                'type': 'scatter',
                'fill': 'none',
                'connect_points': True,
                'title': _('Datagram'),
                'description': _(
                    '(Lost / Total) datagrams measured by Iperf3 test in UDP mode.'
                ),
                'summary_labels': [
                    _('Lost datagram'),
                    _('Total datagram'),
                ],
                'unit': '',
                'order': 340,
                'query': chart_query['datagram'],
                'colors': [DEFAULT_COLORS[3], DEFAULT_COLORS[2]],
            },
            'datagram_loss': {
                'type': 'scatter',
                'connect_points': True,
                'title': _('Datagram Loss'),
                'description': _(
                    'Indicates datagram loss % during Iperf3 test in UDP mode.'
                ),
                'summary_labels': [
                    _('Datagram loss'),
                ],
                'unit': '%',
                'order': 350,
                'query': chart_query['datagram_loss'],
                'colors': [DEFAULT_COLORS[3]],
            },
        },
    },
}

DEFAULT_CHARTS = {}

DEFAULT_DASHBOARD_TRAFFIC_CHART = {'__all__': ['wan', 'eth1', 'eth0.2']}


def _validate_metric_configuration(metric_config):
    assert 'label' in metric_config
    assert 'name' in metric_config
    assert 'key' in metric_config
    assert 'field_name' in metric_config
    if 'alert_field' in metric_config:
        # ensure only valid alert_field is present
        alert_fields = [metric_config['field_name']] + metric_config['related_fields']
        assert metric_config['alert_field'] in alert_fields


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


def register_metric_notifications(metric_name, metric_config):
    if 'notification' not in metric_config:
        return
    register_notification_type(
        f'{metric_name}_problem', metric_config['notification']['problem']
    )
    register_notification_type(
        f'{metric_name}_recovery', metric_config['notification']['recovery']
    )


def unregister_metric_notifications(metric_name):
    metric_config = DEFAULT_METRICS[metric_name]
    if 'notification' not in metric_config:
        return
    unregister_notification_type(f'{metric_name}_problem')
    unregister_notification_type(f'{metric_name}_recovery')


def get_metric_configuration():
    additional_metrics = deepcopy(app_settings.ADDITIONAL_METRICS)
    for metric_name in list(additional_metrics.keys()):
        if additional_metrics[metric_name].get('partial', False):
            # A partial configuration can be defined in the settings.py
            # with OPENWISP_MONITORING_METRICS setting to override
            # metrics that are added with register_metric method in
            # other django apps.
            # Since, the partial configuration could be defined to
            # override limited fields in the configuration, hence
            # we don't validate the configuration here. Instead.
            # configuration is validated in the register_metric method.
            del additional_metrics[metric_name]
    metrics = deep_merge_dicts(DEFAULT_METRICS, additional_metrics)
    # ensure configuration is not broken
    for metric_config in metrics.values():
        _validate_metric_configuration(metric_config)
    return metrics


def get_metric_configuration_choices():
    metrics = get_metric_configuration()
    choices = []
    for key in sorted(metrics.keys()):
        label = metrics[key]['label']
        choices.append((key, label))
    return choices


def register_metric(metric_name, metric_config):
    """Registers a new metric configuration."""
    if not isinstance(metric_name, str):
        raise ImproperlyConfigured('Metric configuration name should be type "str".')
    if not isinstance(metric_config, dict):
        raise ImproperlyConfigured('Metric configuration should be type "dict".')
    if metric_name in DEFAULT_METRICS:
        raise ImproperlyConfigured(
            f'{metric_name} is an already registered Metric Configuration.'
        )
    if metric_name in app_settings.ADDITIONAL_METRICS:
        # There is partial configuration present for this "metric_name" in
        # ADDITIONAL_METRICS. We need to merge the partial configuration with
        # the registered metric before validating. Otherwise, users won't be
        # able to override registered metrics using OPENWISP_MONITORING_METRICS
        # setting.
        metric_config = deep_merge_dicts(
            metric_config,
            app_settings.ADDITIONAL_METRICS[metric_name],
        )
        metric_config.pop('partial', None)
    _validate_metric_configuration(metric_config)
    for chart in metric_config.get('charts', {}).values():
        _validate_chart_configuration(chart_config=chart)
    DEFAULT_METRICS.update({metric_name: metric_config})
    _register_metric_configuration_choice(metric_name, metric_config)
    register_metric_notifications(metric_name, metric_config)


def unregister_metric(metric_name):
    if not isinstance(metric_name, str):
        raise ImproperlyConfigured('Metric configuration name should be type "str".')
    if metric_name not in DEFAULT_METRICS:
        raise ImproperlyConfigured(f'No such Chart configuation "{metric_name}".')
    unregister_metric_notifications(metric_name)
    DEFAULT_METRICS.pop(metric_name)
    _unregister_metric_configuration_choice(metric_name)


def _register_metric_configuration_choice(metric_name, metric_config):
    name = metric_config.get('label', metric_name)
    METRIC_CONFIGURATION_CHOICES.append((metric_name, name))


def _unregister_metric_configuration_choice(metric_name):
    for index, (key, name) in enumerate(METRIC_CONFIGURATION_CHOICES):
        if key == metric_name:
            METRIC_CONFIGURATION_CHOICES.pop(index)
            return


def get_chart_configuration():
    metrics = get_metric_configuration()
    for metric in metrics.values():
        if 'charts' in metric:
            DEFAULT_CHARTS.update(metric['charts'])
    charts = deep_merge_dicts(DEFAULT_CHARTS, app_settings.ADDITIONAL_CHARTS)
    # ensure configuration is not broken
    for key, options in charts.items():
        _validate_chart_configuration(options)
    return charts


def get_chart_configuration_choices():
    charts = get_chart_configuration()
    choices = []
    for key in sorted(charts.keys()):
        label = charts[key].get('label', charts[key]['title'])
        choices.append((key, label))
    return choices


def register_chart(chart_name, chart_config):
    """Registers a new chart configuration."""
    if not isinstance(chart_name, str):
        raise ImproperlyConfigured('Chart name should be type "str".')
    if not isinstance(chart_config, dict):
        raise ImproperlyConfigured('Chart configuration should be type "dict".')
    if chart_name in get_chart_configuration():
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
    name = chart_config.get('label', chart_name)
    CHART_CONFIGURATION_CHOICES.append((chart_name, name))


def _unregister_chart_configuration_choice(chart_name):
    for index, (key, name) in enumerate(CHART_CONFIGURATION_CHOICES):
        if key == chart_name:
            CHART_CONFIGURATION_CHOICES.pop(index)
            return


def _clean_dashboard_traffic_chart():
    for interfaces in DEFAULT_DASHBOARD_TRAFFIC_CHART.values():
        for index in range(len(interfaces)):
            interfaces[index] = clean_timeseries_data_key(interfaces[index])


DEFAULT_DASHBOARD_TRAFFIC_CHART.update(app_settings.ADDITIONAL_DASHBOARD_TRAFFIC_CHART)
_clean_dashboard_traffic_chart()
METRIC_CONFIGURATION_CHOICES = get_metric_configuration_choices()
CHART_CONFIGURATION_CHOICES = get_chart_configuration_choices()
