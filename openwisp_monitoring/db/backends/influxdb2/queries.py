chart_query = {
    'uptime': {
        'influxdb2': (
            'from(bucket: "{key}") '
            '|> range(start: {time}{end_date}) '
            '|> filter(fn: (r) => r["_measurement"] == "{field_name}" and '
            'r["content_type"] == "{content_type}" and r["object_id"] == "{object_id}") '
            '|> mean() '
            '|> map(fn: (r) => ({ r with uptime: r._value * 100 }))'
        )
    },
    'packet_loss': {
        'influxdb2': (
            'from(bucket: "{key}") '
            '|> range(start: {time}{end_date}) '
            '|> filter(fn: (r) => r["_measurement"] == "loss" and '
            'r["content_type"] == "{content_type}" and r["object_id"] == "{object_id}") '
            '|> mean()'
        )
    },
    'rtt': {
        'influxdb2': (
            'from(bucket: "{key}") '
            '|> range(start: {time}{end_date}) '
            '|> filter(fn: (r) => r["_measurement"] == "rtt_avg" and '
            'r["content_type"] == "{content_type}" and r["object_id"] == "{object_id}") '
            '|> mean() '
            '|> yield(name: "RTT_average") '
            'from(bucket: "{key}") '
            '|> range(start: {time}{end_date}) '
            '|> filter(fn: (r) => r["_measurement"] == "rtt_max" and '
            'r["content_type"] == "{content_type}" and r["object_id"] == "{object_id}") '
            '|> mean() '
            '|> yield(name: "RTT_max") '
            'from(bucket: "{key}") '
            '|> range(start: {time}{end_date}) '
            '|> filter(fn: (r) => r["_measurement"] == "rtt_min" and '
            'r["content_type"] == "{content_type}" and r["object_id"] == "{object_id}") '
            '|> mean() '
            '|> yield(name: "RTT_min")'
        )
    },
    'wifi_clients': {
        'influxdb2': (
            'from(bucket: "{key}") '
            '|> range(start: {time}{end_date}) '
            '|> filter(fn: (r) => r["_measurement"] == "{field_name}" and '
            'r["content_type"] == "{content_type}" and r["object_id"] == "{object_id}" and '
            'r["ifname"] == "{ifname}") '
            '|> distinct() '
            '|> count()'
        )
    },
    'general_wifi_clients': {
        'influxdb2': (
            'from(bucket: "{key}") '
            '|> range(start: {time}{end_date}) '
            '|> filter(fn: (r) => r["_measurement"] == "{field_name}"'
            '{organization_id}{location_id}{floorplan_id}) '
            '|> distinct() '
            '|> count()'
        )
    },
    'traffic': {
        'influxdb2': (
            'from(bucket: "{key}") '
            '|> range(start: {time}{end_date}) '
            '|> filter(fn: (r) => r["_measurement"] == "tx_bytes" and '
            'r["content_type"] == "{content_type}" and r["object_id"] == "{object_id}" and '
            'r["ifname"] == "{ifname}") '
            '|> sum() '
            '|> map(fn: (r) => ({ r with upload: r._value / 1000000000 })) '
            '|> yield(name: "upload") '
            'from(bucket: "{key}") '
            '|> range(start: {time}{end_date}) '
            '|> filter(fn: (r) => r["_measurement"] == "rx_bytes" and '
            'r["content_type"] == "{content_type}" and r["object_id"] == "{object_id}" and '
            'r["ifname"] == "{ifname}") '
            '|> sum() '
            '|> map(fn: (r) => ({ r with download: r._value / 1000000000 })) '
            '|> yield(name: "download")'
        )
    },
    'general_traffic': {
        'influxdb2': (
            'from(bucket: "{key}") '
            '|> range(start: {time}{end_date}) '
            '|> filter(fn: (r) => r["_measurement"] == "tx_bytes"{organization_id}'
            '{location_id}{floorplan_id}{ifname}) '
            '|> sum() '
            '|> map(fn: (r) => ({ r with upload: r._value / 1000000000 })) '
            '|> yield(name: "upload") '
            'from(bucket: "{key}") '
            '|> range(start: {time}{end_date}) '
            '|> filter(fn: (r) => r["_measurement"] == "rx_bytes"{organization_id}'
            '{location_id}{floorplan_id}{ifname}) '
            '|> sum() '
            '|> map(fn: (r) => ({ r with download: r._value / 1000000000 })) '
            '|> yield(name: "download")'
        )
    },
    'memory': {
        'influxdb2': (
            'from(bucket: "{key}") '
            '|> range(start: {time}{end_date}) '
            '|> filter(fn: (r) => r["_measurement"] == "percent_used" and '
            'r["content_type"] == "{content_type}" and r["object_id"] == "{object_id}") '
            '|> mean() '
            '|> map(fn: (r) => ({ r with memory_usage: r._value }))'
        )
    },
    'cpu': {
        'influxdb2': (
            'from(bucket: "{key}") '
            '|> range(start: {time}{end_date}) '
            '|> filter(fn: (r) => r["_measurement"] == "cpu_usage" and '
            'r["content_type"] == "{content_type}" and r["object_id"] == "{object_id}") '
            '|> mean() '
            '|> map(fn: (r) => ({ r with CPU_load: r._value }))'
        )
    },
    'disk': {
        'influxdb2': (
            'from(bucket: "{key}") '
            '|> range(start: {time}{end_date}) '
            '|> filter(fn: (r) => r["_measurement"] == "used_disk" and '
            'r["content_type"] == "{content_type}" and r["object_id"] == "{object_id}") '
            '|> mean() '
            '|> map(fn: (r) => ({ r with disk_usage: r._value }))'
        )
    },
    'signal_strength': {
        'influxdb2': (
            'from(bucket: "{key}") '
            '|> range(start: {time}{end_date}) '
            '|> filter(fn: (r) => r["_measurement"] == "signal_strength" and '
            'r["content_type"] == "{content_type}" and r["object_id"] == "{object_id}") '
            '|> mean() '
            '|> map(fn: (r) => ({ r with signal_strength: round(r._value) })) '
            '|> yield(name: "signal_strength") '
            'from(bucket: "{key}") '
            '|> range(start: {time}{end_date}) '
            '|> filter(fn: (r) => r["_measurement"] == "signal_power" and '
            'r["content_type"] == "{content_type}" and r["object_id"] == "{object_id}") '
            '|> mean() '
            '|> map(fn: (r) => ({ r with signal_power: round(r._value) })) '
            '|> yield(name: "signal_power")'
        )
    },
    'signal_quality': {
        'influxdb2': (
            'from(bucket: "{key}") '
            '|> range(start: {time}{end_date}) '
            '|> filter(fn: (r) => r["_measurement"] == "signal_quality" and '
            'r["content_type"] == "{content_type}" and r["object_id"] == "{object_id}") '
            '|> mean() '
            '|> map(fn: (r) => ({ r with signal_quality: round(r._value) })) '
            '|> yield(name: "signal_quality") '
            'from(bucket: "{key}") '
            '|> range(start: {time}{end_date}) '
            '|> filter(fn: (r) => r["_measurement"] == "snr" and '
            'r["content_type"] == "{content_type}" and r["object_id"] == "{object_id}") '
            '|> mean() '
            '|> map(fn: (r) => ({ r with signal_to_noise_ratio: round(r._value) })) '
            '|> yield(name: "signal_to_noise_ratio")'
        )
    },
    'access_tech': {
        'influxdb2': (
            'from(bucket: "{key}") '
            '|> range(start: {time}{end_date}) '
            '|> filter(fn: (r) => r["_measurement"] == "access_tech" and '
            'r["content_type"] == "{content_type}" and r["object_id"] == "{object_id}") '
            '|> mode() '
            '|> map(fn: (r) => ({ r with access_tech: r._value }))'
        )
    },
    'bandwidth': {
        'influxdb2': (
            'from(bucket: "{key}") '
            '|> range(start: {time}) '
            '|> filter(fn: (r) => r["_measurement"] == "sent_bps_tcp" and '
            'r["content_type"] == "{content_type}" and r["object_id"] == "{object_id}") '
            '|> mean() '
            '|> map(fn: (r) => ({ r with TCP: r._value / 1000000000 })) '
            '|> yield(name: "TCP") '
            'from(bucket: "{key}") '
            '|> range(start: {time}) '
            '|> filter(fn: (r) => r["_measurement"] == "sent_bps_udp" and '
            'r["content_type"] == "{content_type}" and r["object_id"] == "{object_id}") '
            '|> mean() '
            '|> map(fn: (r) => ({ r with UDP: r._value / 1000000000 })) '
            '|> yield(name: "UDP")'
        )
    },
    'transfer': {
        'influxdb2': (
            'from(bucket: "{key}") '
            '|> range(start: {time}) '
            '|> filter(fn: (r) => r["_measurement"] == "sent_bytes_tcp" and '
            'r["content_type"] == "{content_type}" and r["object_id"] == "{object_id}") '
            '|> sum() '
            '|> map(fn: (r) => ({ r with TCP: r._value / 1000000000 })) '
            '|> yield(name: "TCP") '
            'from(bucket: "{key}") '
            '|> range(start: {time}) '
            '|> filter(fn: (r) => r["_measurement"] == "sent_bytes_udp" and '
            'r["content_type"] == "{content_type}" and r["object_id"] == "{object_id}") '
            '|> sum() '
            '|> map(fn: (r) => ({ r with UDP: r._value / 1000000000 })) '
            '|> yield(name: "UDP")'
        )
    },
    'retransmits': {
        'influxdb2': (
            'from(bucket: "{key}") '
            '|> range(start: {time}) '
            '|> filter(fn: (r) => r["_measurement"] == "retransmits" and '
            'r["content_type"] == "{content_type}" and r["object_id"] == "{object_id}") '
            '|> mean() '
            '|> map(fn: (r) => ({ r with retransmits: r._value }))'
        )
    },
    'jitter': {
        'influxdb2': (
            'from(bucket: "{key}") '
            '|> range(start: {time}) '
            '|> filter(fn: (r) => r["_measurement"] == "jitter" and '
            'r["content_type"] == "{content_type}" and r["object_id"] == "{object_id}") '
            '|> mean() '
            '|> map(fn: (r) => ({ r with jitter: r._value }))'
        )
    },
    'datagram': {
        'influxdb2': (
            'from(bucket: "{key}") '
            '|> range(start: {time}) '
            '|> filter(fn: (r) => r["_measurement"] == "lost_packets" and '
            'r["content_type"] == "{content_type}" and r["object_id"] == "{object_id}") '
            '|> mean() '
            '|> map(fn: (r) => ({ r with lost_datagram: r._value })) '
            '|> yield(name: "lost_datagram") '
            'from(bucket: "{key}") '
            '|> range(start: {time}) '
            '|> filter(fn: (r) => r["_measurement"] == "total_packets" and '
            'r["content_type"] == "{content_type}" and r["object_id"] == "{object_id}") '
            '|> mean() '
            '|> map(fn: (r) => ({ r with total_datagram: r._value })) '
            '|> yield(name: "total_datagram")'
        )
    },
    'datagram_loss': {
        'influxdb2': (
            'from(bucket: "{key}") '
            '|> range(start: {time}) '
            '|> filter(fn: (r) => r["_measurement"] == "lost_percent" and '
            'r["content_type"] == "{content_type}" and r["object_id"] == "{object_id}") '
            '|> mean() '
            '|> map(fn: (r) => ({ r with datagram_loss: r._value }))'
        )
    },
}

default_chart_query = [
    'from(bucket: "{key}") |> range(start: {time}{end_date}) ',
    (
        '|> filter(fn: (r) => r["_measurement"] == "{field_name}" and '
        'r["content_type"] == "{content_type}" and r["object_id"] == "{object_id}")'
    ),
]

device_data_query = (
    'from(bucket: "{0}") |> range(start: 0) '
    '|> filter(fn: (r) => r["_measurement"] == "{1}" and r["pk"] == "{2}") '
    '|> sort(columns: ["_time"], desc: true) '
    '|> limit(n: 1)'
)
