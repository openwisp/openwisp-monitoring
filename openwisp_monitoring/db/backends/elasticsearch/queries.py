import operator
from copy import deepcopy

from openwisp_utils.utils import deep_merge_dicts

from .settings import ADDITIONAL_CHART_OPERATIONS

default_chart_query = {
    'query': {
        'nested': {
            'path': 'tags',
            'query': {
                'bool': {
                    'must': [
                        {'match': {'tags.object_id': {'query': '{object_id}'}}},
                        {'match': {'tags.content_type': {'query': '{content_type}'}}},
                    ]
                }
            },
        },
    },
    '_source': False,
    'size': 0,
    'aggs': {
        'GroupByTime': {
            'nested': {
                'path': 'points',
                'aggs': {
                    'set_range': {
                        'filter': {
                            'range': {
                                'points.time': {'from': 'now-1d/d', 'to': 'now/d'}
                            }
                        },
                        'aggs': {
                            'time': {
                                'date_histogram': {
                                    'field': 'points.time',
                                    'fixed_interval': '10m',
                                    'format': 'date_time_no_millis',
                                    'order': {'_key': 'desc'},
                                },
                                'aggs': {
                                    'nest': {
                                        'nested': {
                                            'path': 'points.fields',
                                            'aggs': {
                                                '{field_name}': {
                                                    'avg': {
                                                        'field': 'points.fields.{field_name}'
                                                    }
                                                }
                                            },
                                        }
                                    },
                                },
                            },
                        },
                    }
                },
            }
        }
    },
}

math_map = {
    'uptime': {'operator': '*', 'value': 100},
    'memory_usage': {'operator': '*', 'value': 100},
    'CPU_load': {'operator': '*', 'value': 100},
    'disk_usage': {'operator': '*', 'value': 100},
    'upload': {'operator': '/', 'value': 1000000000},
    'download': {'operator': '/', 'value': 1000000000},
}

operator_lookup = {
    '+': operator.add,
    '-': operator.sub,
    '*': operator.mul,
    '/': operator.truediv,
}

if ADDITIONAL_CHART_OPERATIONS:
    assert isinstance(ADDITIONAL_CHART_OPERATIONS, dict)
    for value in ADDITIONAL_CHART_OPERATIONS.values():
        assert value['operator'] in operator_lookup
        assert isinstance(value['value'], (int, float))
    math_map = deep_merge_dicts(math_map, ADDITIONAL_CHART_OPERATIONS)


def _make_query(aggregation=None):
    query = deepcopy(default_chart_query)
    if aggregation:
        query['aggs']['GroupByTime']['nested']['aggs']['set_range']['aggs']['time'][
            'aggs'
        ]['nest']['nested']['aggs'] = aggregation
    return query


def _get_chart_query():
    aggregation_dict = {
        'uptime': {'uptime': {'avg': {'field': 'points.fields.reachable'}}},
        'packet_loss': {'packet_loss': {'avg': {'field': 'points.fields.loss'}}},
        'rtt': {
            'RTT_average': {'avg': {'field': 'points.fields.rtt_avg'}},
            'RTT_max': {'avg': {'field': 'points.fields.rtt_max'}},
            'RTT_min': {'avg': {'field': 'points.fields.rtt_min'}},
        },
        'traffic': {
            'upload': {'sum': {'field': 'points.fields.tx_bytes'}},
            'download': {'sum': {'field': 'points.fields.rx_bytes'}},
        },
        'wifi_clients': {
            'wifi_clients': {
                'cardinality': {
                    'field': 'points.fields.{field_name}.keyword',
                    'missing': 0,
                }
            }
        },
        'memory': {'memory_usage': {'avg': {'field': 'points.fields.percent_used'}}},
        'cpu': {'CPU_load': {'avg': {'field': 'points.fields.cpu_usage'}}},
        'disk': {'disk_usage': {'avg': {'field': 'points.fields.used_disk'}}},
    }
    query = {}
    for key, value in aggregation_dict.items():
        query[key] = {'elasticsearch': _make_query(value)}
    return query


chart_query = _get_chart_query()
