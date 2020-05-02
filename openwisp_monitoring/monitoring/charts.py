from django.utils.translation import ugettext_lazy as _
from netjsonconfig.utils import merge_config

from . import settings as app_settings

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
        'order': 100,
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
        'order': 101,
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
        'order': 102,
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
        'summary_labels': [_('Total WiFi clients')],
        'unit': f' {_("wifi clients")}',
        'order': 110,
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
        'summary_labels': [_('Total upload traffic'), _('Total download traffic')],
        'unit': f' {_("GB")}',
        'order': 111,
        'query': {
            'influxdb': (
                "SELECT SUM(tx_bytes) / 1000000000 AS upload, "
                "SUM(rx_bytes) / 1000000000 AS download FROM {key} "
                "WHERE time >= '{time}' AND content_type = '{content_type}' "
                "AND object_id = '{object_id}' GROUP BY time(1d)"
            )
        },
    },
    'qoe': {
        'type': 'scatter',
        'title': _('Quality of Experience'),
        'description': _(
            'The Quality of Experience (QoE) score rates '
            'the quality of the internet connection.'
        ),
        'summary_labels': [_('Average QoE score')],
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
        label = charts[key].get('label', charts[key]['title'])
        choices.append((key, label))
    return choices
