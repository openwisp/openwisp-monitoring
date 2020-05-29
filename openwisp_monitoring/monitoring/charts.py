from django.utils.translation import ugettext_lazy as _

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
        'query': {
            'influxdb': (
                "SELECT MEAN({field_name})*100 AS uptime FROM {key} WHERE "
                "time >= '{time}' AND content_type = '{content_type}' AND "
                "object_id = '{object_id}' GROUP BY time(1d)"
            )
        },
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
        'query': {
            'influxdb': (
                "SELECT MEAN(loss) AS packet_loss FROM {key} WHERE "
                "time >= '{time}' AND content_type = '{content_type}' AND "
                "object_id = '{object_id}' GROUP BY time(1d)"
            )
        },
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
        'query': {
            'influxdb': (
                "SELECT MEAN(rtt_avg) AS RTT_average, MEAN(rtt_max) AS "
                "RTT_max, MEAN(rtt_min) AS RTT_min FROM {key} WHERE "
                "time >= '{time}' AND content_type = '{content_type}' AND "
                "object_id = '{object_id}' GROUP BY time(1d)"
            )
        },
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
        'query': {
            'influxdb': (
                "SELECT COUNT(DISTINCT({field_name})) AS wifi_clients FROM {key} "
                "WHERE time >= '{time}' AND content_type = '{content_type}' "
                "AND object_id = '{object_id}' GROUP BY time(1d)"
            )
        },
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
        'query': {
            'influxdb': (
                "SELECT SUM(tx_bytes) / 1000000000 AS upload, "
                "SUM(rx_bytes) / 1000000000 AS download FROM {key} "
                "WHERE time >= '{time}' AND content_type = '{content_type}' "
                "AND object_id = '{object_id}' GROUP BY time(1d)"
            )
        },
    },
    'memory': {
        'type': 'scatter',
        'title': _('Memory Usage'),
        'description': _('Percentage of memory (RAM) being used.'),
        'summary_labels': [_('Memory Usage')],
        'unit': '%',
        'colors': [DEFAULT_COLORS[4]],
        'order': 250,
        'query': {
            'influxdb': (
                "SELECT 100 * (1 - ((MEDIAN(free_memory) + MEDIAN(buffered_memory)) "
                "/ MEDIAN(total_memory))) AS memory_usage "
                "FROM {key} WHERE time >= '{time}' AND content_type = '{content_type}' "
                "AND object_id = '{object_id}' GROUP BY time(1d)"
            )
        },
    },
    'load': {
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
        'query': {
            'influxdb': (
                "SELECT 100 * MEAN(load_1) AS CPU_load FROM {key} WHERE "
                "time >= '{time}' AND content_type = '{content_type}' AND "
                "object_id = '{object_id}' GROUP BY time(1d)"
            )
        },
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
        'query': {
            'influxdb': (
                "SELECT 100 * MEAN(used_disk) AS disk_usage FROM {key} WHERE "
                "time >= '{time}' AND content_type = '{content_type}' AND "
                "object_id = '{object_id}' GROUP BY time(1d)"
            )
        },
    },
}


def deep_merge_dicts(dict1, dict2):
    result = dict1.copy()
    for key, value in dict2.items():
        if isinstance(value, dict):
            node = result.get(key, {})
            result[key] = deep_merge_dicts(node, value)
        else:
            result[key] = value
    return result


def get_chart_configuration():
    charts = deep_merge_dicts(DEFAULT_CHARTS, app_settings.ADDITIONAL_CHARTS)
    # ensure configuration is not broken
    for key, options in charts.items():
        assert 'type' in options
        assert 'title' in options
        assert 'description' in options
        assert 'order' in options
        assert 'query' in options
        if options['query'] is not None:
            assert isinstance(options['query'], dict)
            assert 'influxdb' in options['query']
        else:
            assert 'unit' in options
        if 'colorscale' in options:
            assert 'max' in options['colorscale']
            assert 'min' in options['colorscale']
            assert 'label' in options['colorscale']
            assert 'scale' in options['colorscale']
    return charts


def get_chart_configuration_choices():
    charts = get_chart_configuration()
    choices = []
    for key in sorted(charts.keys()):
        label = charts[key].get('label', charts[key]['title'])
        choices.append((key, label))
    return choices
