from django.utils.translation import ugettext_lazy as _
from netjsonconfig.utils import merge_config

from . import settings as app_settings

DEFAULT_CHARTS = {
    'uptime': {
        'type': 'line',
        'title': _('Uptime'),
        'description': _(
            '100% means reachable, 0% means unreachable, a value in between '
            'indicates the average reachability in the period observed.'
            'Obtained with the fping linux program.'
        ),
        'unit': '%',
        'order': 100,
        'query': {
            'influxdb': (
                "SELECT MEAN({field_name})*100 AS uptime FROM {key} WHERE "
                "time >= '{time}' AND content_type = '{content_type}' AND "
                "object_id = '{object_id}' GROUP BY time(1d) fill(0)"
            )
        },
    },
    'packet_loss': {
        'type': 'line',
        'title': _('Packet loss'),
        'description': _(
            'Indicates the percentage of lost packets observed in ICMP probes '
            'Obtained with the fping linux program.'
        ),
        'unit': '%',
        'order': 101,
        'query': {
            'influxdb': (
                "SELECT MEAN(loss) AS packet_loss FROM {key} WHERE "
                "time >= '{time}' AND content_type = '{content_type}' AND "
                "object_id = '{object_id}' GROUP BY time(1d) fill(0)"
            )
        },
    },
    'rtt': {
        'type': 'line',
        'title': _('Round Trip Time'),
        'description': _('Round trip time of ICMP probes.'),
        'unit': _('ms'),
        'order': 102,
        'query': {
            'influxdb': (
                "SELECT MEAN(rtt_avg) AS RTT_average, MEAN(rtt_max) AS "
                "RTT_max, MEAN(rtt_min) AS RTT_min FROM {key} WHERE "
                "time >= '{time}' AND content_type = '{content_type}' AND "
                "object_id = '{object_id}' GROUP BY time(1d) fill(0)"
            )
        },
    },
    'wifi_clients': {
        'type': 'line',
        'title': _('{metric.key} wifi clients'),
        'description': _('WiFi clients associated to {metric.key}.'),
        'unit': _('wifi clients'),
        'order': 110,
        'query': {
            'influxdb': (
                "SELECT COUNT(DISTINCT({field_name})) AS wifi_clients FROM {key} "
                "WHERE time >= '{time}' AND content_type = '{content_type}' "
                "AND object_id = '{object_id}' GROUP BY time(1d) fill(0)"
            )
        },
    },
    'traffic': {
        'type': 'line',
        'title': _('{metric.key} traffic'),
        'description': _(
            'Network traffic (download and upload) on interface {metric.key}.'
        ),
        'unit': _('GB'),
        'order': 111,
        'query': {
            'influxdb': (
                "SELECT SUM(tx_bytes) / 1000000000 AS upload, "
                "SUM(rx_bytes) / 1000000000 AS download FROM {key} "
                "WHERE time >= '{time}' AND content_type = '{content_type}' "
                "AND object_id = '{object_id}' GROUP BY time(1d) fill(0)"
            )
        },
    },
    'qoe': {
        'type': 'line',
        'title': _('Quality of Experience'),
        'description': _('QoE score.'),
        'unit': _('%'),
        'order': 112,
        'query': {
            'influxdb': (
                "SELECT MEAN({field_name}) AS qoe FROM {key} "
                "WHERE time >= '{time}' AND content_type = '{content_type}' "
                "AND object_id = '{object_id}' GROUP BY time(1d)"
            )
        },
    },
}


def get_chart_configuration():
    charts = merge_config(DEFAULT_CHARTS, app_settings.ADDITIONAL_CHARTS)
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
        if options['type'] == 'histogram':
            assert options['top_fields']
        else:
            assert 'unit' in options
    return charts


def get_chart_configuration_choices():
    charts = get_chart_configuration()
    choices = []
    for key in sorted(charts.keys()):
        choices.append((key, charts[key]['title']))
    return choices
