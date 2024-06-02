import logging

logger = logging.getLogger(__name__)

chart_query = {
    'uptime': {
        'influxdb2': '''
            from(bucket: "{key}")
                |> range(start: {time}{end_date})
                |> filter(fn: (r) => r._measurement == "{content_type}" and r.object_id == "{object_id}")
                |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)
                |> map(fn: (r) => ({ r with _value: r._value * 100 }))
                |> rename(columns: {_value: "uptime"})

        '''
    },
    'packet_loss': {
        'influxdb2': '''
            from(bucket: "{key}")
                |> range(start: {time}{end_date})
                |> filter(fn: (r) => r._measurement == "{content_type}" and r.object_id == "{object_id}")
                |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)
                |> rename(columns: {_value: "packet_loss"})

        '''
    },
    'rtt': {
        'influxdb2': '''
            from(bucket: "{key}")
                |> range(start: {time}{end_date})
                |> filter(fn: (r) => r._measurement == "{content_type}" && r.object_id == "{object_id}")
                |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)
                |> map(fn: (r) => ({
                    RTT_average: r.rtt_avg,
                    RTT_max: r.rtt_max,
                    RTT_min: r.rtt_min
                }))
        '''
    },
    'wifi_clients': {
        'influxdb2': '''
            from(bucket: "{key}")
                |> range(start: {time}{end_date})
                |> filter(fn: (r) => r._measurement == "{content_type}" &&
                                     r.object_id == "{object_id}" && r.ifname == "{ifname}")
                |> group(columns: ["{field_name}"])
                |> count(column: "{field_name}")
                |> map(fn: (r) => ({ r with wifi_clients: r._value }))
                |> group() // Ungroup to summarize across the selected range
        '''
    },
    'general_wifi_clients': {
        'influxdb2': '''
            from(bucket: "{key}")
                |> range(start: {time}{end_date})
                |> filter(fn: (r) => r.organization_id == "{organization_id}" &&
                                     r.location_id == "{location_id}" && r.floorplan_id == "{floorplan_id}")
                |> group(columns: ["{field_name}"])
                |> count(column: "{field_name}")
                |> map(fn: (r) => ({ r with wifi_clients: r._value }))
                |> group() // Ungroup to summarize across the selected range
        '''
    },
    'traffic': {
        'influxdb2': '''
            from(bucket: "{key}")
                |> range(start: {time}{end_date})
                |> filter(fn: (r) => r._measurement == "{content_type}" &&
                                     r.object_id == "{object_id}" && r.ifname == "{ifname}")
                |> aggregateWindow(every: 1d, fn: sum, createEmpty: false)
                |> map(fn: (r) => ({
                    upload: r.tx_bytes / 1000000000,
                    download: r.rx_bytes / 1000000000
                }))
        '''
    },
    'general_traffic': {
        'influxdb2': '''
            from(bucket: "{key}")
                |> range(start: {time}{end_date})
                |> filter(fn: (r) => r.organization_id == "{organization_id}" &&
                                     r.location_id == "{location_id}" &&
                                     r.floorplan_id == "{floorplan_id}" && r.ifname == "{ifname}")
                |> aggregateWindow(every: 1d, fn: sum, createEmpty: false)
                |> map(fn: (r) => ({
                    upload: r.tx_bytes / 1000000000,
                    download: r.rx_bytes / 1000000000
                }))
        '''
    },
    'memory': {
        'influxdb2': '''
            from(bucket: "{key}")
                |> range(start: {time}{end_date})
                |> filter(fn: (r) => r._measurement == "{content_type}" && r.object_id == "{object_id}")
                |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)
                |> map(fn: (r) => ({
                    memory_usage: r.percent_used
                }))
        '''
    },
    'cpu': {
        'influxdb2': '''
            from(bucket: "{key}")
                |> range(start: {time}{end_date})
                |> filter(fn: (r) => r._measurement == "{content_type}" && r.object_id == "{object_id}")
                |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)
                |> map(fn: (r) => ({
                    CPU_load: r.cpu_usage
                }))
        '''
    },
    'disk': {
        'influxdb2': '''
            from(bucket: "{key}")
                |> range(start: {time}{end_date})
                |> filter(fn: (r) => r._measurement == "{content_type}" && r.object_id == "{object_id}")
                |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)
                |> map(fn: (r) => ({
                    disk_usage: r.used_disk
                }))
        '''
    },
    'signal_strength': {
        'influxdb2': '''
            from(bucket: "{key}")
                |> range(start: {time}{end_date})
                |> filter(fn: (r) => r._measurement == "{content_type}" && r.object_id == "{object_id}")
                |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)
                |> map(fn: (r) => ({
                    signal_strength: math.round(r.signal_strength),
                    signal_power: math.round(r.signal_power)
                 }))

        '''
    },
    'signal_quality': {
        'influxdb2': '''
            from(bucket: "{key}")
                |> range(start: {time}{end_date})
                |> filter(fn: (r) => r._measurement == "{content_type}" && r.object_id == "{object_id}")
                |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)
                |> map(fn: (r) => ({
                    signal_quality: math.round(r.signal_quality),
                    signal_to_noise_ratio: math.round(r.snr)
                }))
        '''
    },
    'access_tech': {
        'influxdb2': '''
            from(bucket: "{key}")
                |> range(start: {time}{end_date})
                |> filter(fn: (r) => r._measurement == "{content_type}" && r.object_id == "{object_id}")
                |> aggregateWindow(every: 1d, fn: mode, createEmpty: false)
                |> map(fn: (r) => ({
                    access_tech: r.access_tech
                }))
        '''
    },
    'bandwidth': {
        'influxdb2': '''
            from(bucket: "{key}")
                |> range(start: {time})
                |> filter(fn: (r) => r._measurement == "{content_type}" && r.object_id == "{object_id}")
                |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)
                |> map(fn: (r) => ({
                    TCP: r.sent_bps_tcp / 1000000000,
                    UDP: r.sent_bps_udp / 1000000000
                }))
        '''
    },
    'transfer': {
        'influxdb2': '''
            from(bucket: "{key}")
                |> range(start: {time})
                |> filter(fn: (r) => r._measurement == "{content_type}" && r.object_id == "{object_id}")
                |> aggregateWindow(every: 1d, fn: sum, createEmpty: false)
                |> map(fn: (r) => ({
                    TCP: r.sent_bytes_tcp / 1000000000,
                    UDP: r.sent_bytes_udp / 1000000000
                }))
        '''
    },
    'retransmits': {
        'influxdb2': '''
            from(bucket: "{key}")
                |> range(start: {time})
                |> filter(fn: (r) => r._measurement == "{content_type}" && r.object_id == "{object_id}")
                |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)
                |> map(fn: (r) => ({
                    retransmits: r.retransmits
                }))
        '''
    },
    'jitter': {
        'influxdb2': '''
            from(bucket: "{key}")
                |> range(start: {time})
                |> filter(fn: (r) => r._measurement == "{content_type}" && r.object_id == "{object_id}")
                |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)
                |> map(fn: (r) => ({
                    jitter: r.jitter
                }))
        '''
    },
    'datagram': {
        'influxdb2': '''
            from(bucket: "{key}")
                |> range(start: {time})
                |> filter(fn: (r) => r._measurement == "{content_type}" && r.object_id == "{object_id}")
                |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)
                |> map(fn: (r) => ({
                    lost_datagram: r.lost_packets,
                    total_datagram: r.total_packets
                  }))
        '''
    },
    'datagram_loss': {
        'influxdb2': '''
            from(bucket: "{key}")
                |> range(start: {time})
                |> filter(fn: (r) => r._measurement == "{content_type}" && r.object_id == "{object_id}")
                |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)
                |> map(fn: (r) => ({
                    datagram_loss: r.lost_percent
                }))
        '''
    },
}

default_chart_query = '''
    from(bucket: "{key}")
        |> range(start: {time}{end_date})
        |> filter(fn: (r) =>
            r._measurement == "{content_type}" &&
            r.object_id == "{object_id}"
        )
        |> keep(columns: ["{field_name}"])
'''

device_data_query = '''
    from(bucket: "{key}")
        |> range(start: -inf)
        |> filter(fn: (r) =>
            r._measurement == "{content_type}" &&
            r.pk == "{pk}"
        )
        |> last()
'''


def get_chart_query(chart_type, **params):
    """Fetches and formats a specific chart query based on the chart type and provided parameters."""
    try:
        query = chart_query[chart_type].format(**params)
    except KeyError:
        logger.warning(
            f"No specific query found for chart type '{chart_type}'. Using default query."
        )
        query = default_chart_query.format(**params)
    return query


def get_device_data_query(**params):
    """Formats the device data query based on provided parameters."""
    return device_data_query.format(**params)
