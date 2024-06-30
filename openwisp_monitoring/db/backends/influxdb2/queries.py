chart_query = {
    'uptime': {
        'influxdb2': (
            'from(bucket: "mybucket")'
            '  |> range(start: {time}, stop: {end_date})'
            '  |> filter(fn: (r) => r._measurement == "{measurement}")'
            '  |> filter(fn: (r) => r._field == "{field_name}")'
            '  |> filter(fn: (r) => r.content_type == "{content_type}")'
            '  |> filter(fn: (r) => r.object_id == "{object_id}")'
            '  |> mean()'
            '  |> map(fn: (r) => ({ r with _value: r._value * 100.0 }))'
            '  |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)'
            '  |> yield(name: "uptime")'
        )
    },
    'packet_loss': {
        'influxdb2': (
            'from(bucket: "mybucket")'
            '  |> range(start: {time}, stop: {end_date})'
            '  |> filter(fn: (r) => r._measurement == "{measurement}")'
            '  |> filter(fn: (r) => r._field == "loss")'
            '  |> filter(fn: (r) => r.content_type == "{content_type}")'
            '  |> filter(fn: (r) => r.object_id == "{object_id}")'
            '  |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)'
            '  |> yield(name: "packet_loss")'
        )
    },
    'rtt': {
        'influxdb2': (
            'from(bucket: "mybucket")'
            '  |> range(start: {time}, stop: {end_date})'
            '  |> filter(fn: (r) => r._measurement == "{measurement}")'
            '  |> filter(fn: (r) => r._field == "rtt_avg" or r._field == "rtt_max" or r._field == "rtt_min")'
            '  |> filter(fn: (r) => r.content_type == "{content_type}")'
            '  |> filter(fn: (r) => r.object_id == "{object_id}")'
            '  |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)'
            '  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")'
            '  |> yield(name: "rtt")'
        )
    },
    'wifi_clients': {
        'influxdb2': (
            'from(bucket: "mybucket")'
            '  |> range(start: {time}, stop: {end_date})'
            '  |> filter(fn: (r) => r._measurement == "{measurement}")'
            '  |> filter(fn: (r) => r._field == "{field_name}")'
            '  |> filter(fn: (r) => r.content_type == "{content_type}")'
            '  |> filter(fn: (r) => r.object_id == "{object_id}")'
            '  |> filter(fn: (r) => r.ifname == "{ifname}")'
            '  |> group()'
            '  |> distinct()'
            '  |> count()'
            '  |> set(key: "_field", value: "wifi_clients")'
            '  |> aggregateWindow(every: 1d, fn: max)'
        )
    },
    'general_wifi_clients': {
        'influxdb2': (
            'from(bucket: "mybucket")'
            '  |> range(start: {time}, stop: {end_date})'
            '  |> filter(fn: (r) => r._measurement == "{measurement}")'
            '  |> filter(fn: (r) => r._field == "{field_name}")'
            '  |> filter(fn: (r) => r.organization_id == "{organization_id}")'
            '  |> filter(fn: (r) => r.location_id == "{location_id}")'
            '  |> filter(fn: (r) => r.floorplan_id == "{floorplan_id}")'
            '  |> group()'
            '  |> distinct()'
            '  |> count()'
            '  |> set(key: "_field", value: "wifi_clients")'
            '  |> aggregateWindow(every: 1d, fn: max)'
        )
    },
    'traffic': {
        'influxdb2': (
            'from(bucket: "mybucket")'
            '  |> range(start: {time}, stop: {end_date})'
            '  |> filter(fn: (r) => r._measurement == "{measurement}")'
            '  |> filter(fn: (r) => r._field == "tx_bytes" or r._field == "rx_bytes")'
            '  |> filter(fn: (r) => r.content_type == "{content_type}")'
            '  |> filter(fn: (r) => r.object_id == "{object_id}")'
            '  |> filter(fn: (r) => r.ifname == "{ifname}")'
            '  |> sum()'
            '  |> map(fn: (r) => ({ r with _value: r._value / 1000000000.0 }))'
            '  |> aggregateWindow(every: 1d, fn: sum, createEmpty: false)'
            '  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")'
            '  |> rename(columns: {tx_bytes: "upload", rx_bytes: "download"})'
            '  |> yield(name: "traffic")'
        )
    },
    'general_traffic': {
        'influxdb2': (
            'from(bucket: "mybucket")'
            '  |> range(start: {time}, stop: {end_date})'
            '  |> filter(fn: (r) => r._measurement == "{measurement}")'
            '  |> filter(fn: (r) => r._field == "tx_bytes" or r._field == "rx_bytes")'
            '  |> filter(fn: (r) => r.organization_id == "{organization_id}")'
            '  |> filter(fn: (r) => r.location_id == "{location_id}")'
            '  |> filter(fn: (r) => r.floorplan_id == "{floorplan_id}")'
            '  |> filter(fn: (r) => r.ifname == "{ifname}")'
            '  |> sum()'
            '  |> map(fn: (r) => ({ r with _value: r._value / 1000000000.0 }))'
            '  |> aggregateWindow(every: 1d, fn: sum, createEmpty: false)'
            '  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")'
            '  |> rename(columns: {tx_bytes: "upload", rx_bytes: "download"})'
            '  |> yield(name: "general_traffic")'
        )
    },
    'memory': {
        'influxdb2': (
            'from(bucket: "mybucket")'
            '  |> range(start: {time}, stop: {end_date})'
            '  |> filter(fn: (r) => r._measurement == "{measurement}")'
            '  |> filter(fn: (r) => r._field == "percent_used")'
            '  |> filter(fn: (r) => r.content_type == "{content_type}")'
            '  |> filter(fn: (r) => r.object_id == "{object_id}")'
            '  |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)'
            '  |> yield(name: "memory_usage")'
        )
    },
    'cpu': {
        'influxdb2': (
            'from(bucket: "mybucket")'
            '  |> range(start: {time}, stop: {end_date})'
            '  |> filter(fn: (r) => r._measurement == "{measurement}")'
            '  |> filter(fn: (r) => r._field == "cpu_usage")'
            '  |> filter(fn: (r) => r.content_type == "{content_type}")'
            '  |> filter(fn: (r) => r.object_id == "{object_id}")'
            '  |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)'
            '  |> yield(name: "CPU_load")'
        )
    },
    'disk': {
        'influxdb2': (
            'from(bucket: "mybucket")'
            '  |> range(start: {time}, stop: {end_date})'
            '  |> filter(fn: (r) => r._measurement == "{measurement}")'
            '  |> filter(fn: (r) => r._field == "used_disk")'
            '  |> filter(fn: (r) => r.content_type == "{content_type}")'
            '  |> filter(fn: (r) => r.object_id == "{object_id}")'
            '  |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)'
            '  |> yield(name: "disk_usage")'
        )
    },
    'signal_strength': {
        'influxdb2': (
            'from(bucket: "mybucket")'
            '  |> range(start: {time}, stop: {end_date})'
            '  |> filter(fn: (r) => r._measurement == "{measurement}")'
            '  |> filter(fn: (r) => r._field == "signal_strength" or r._field == "signal_power")'
            '  |> filter(fn: (r) => r.content_type == "{content_type}")'
            '  |> filter(fn: (r) => r.object_id == "{object_id}")'
            '  |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)'
            '  |> map(fn: (r) => ({ r with _value: float(v: int(v: r._value)) }))'
            '  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")'
            '  |> yield(name: "signal_strength")'
        )
    },
    'signal_quality': {
        'influxdb2': (
            'from(bucket: "mybucket")'
            '  |> range(start: {time}, stop: {end_date})'
            '  |> filter(fn: (r) => r._measurement == "{measurement}")'
            '  |> filter(fn: (r) => r._field == "signal_quality" or r._field == "snr")'
            '  |> filter(fn: (r) => r.content_type == "{content_type}")'
            '  |> filter(fn: (r) => r.object_id == "{object_id}")'
            '  |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)'
            '  |> map(fn: (r) => ({ r with _value: float(v: int(v: r._value)) }))'
            '  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")'
            '  |> yield(name: "signal_quality")'
        )
    },
    'access_tech': {
        'influxdb2': (
            'from(bucket: "mybucket")'
            '  |> range(start: {time}, stop: {end_date})'
            '  |> filter(fn: (r) => r._measurement == "{measurement}")'
            '  |> filter(fn: (r) => r._field == "access_tech")'
            '  |> filter(fn: (r) => r.content_type == "{content_type}")'
            '  |> filter(fn: (r) => r.object_id == "{object_id}")'
            '  |> aggregateWindow(every: 1d, fn: (column) => mode(column: "_value"), createEmpty: false)'
            '  |> yield(name: "access_tech")'
        )
    },
    'bandwidth': {
        'influxdb2': (
            'from(bucket: "mybucket")'
            '  |> range(start: {time}, stop: {end_date})'
            '  |> filter(fn: (r) => r._measurement == "{measurement}")'
            '  |> filter(fn: (r) => r._field == "sent_bps_tcp" or r._field == "sent_bps_udp")'
            '  |> filter(fn: (r) => r.content_type == "{content_type}")'
            '  |> filter(fn: (r) => r.object_id == "{object_id}")'
            '  |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)'
            '  |> map(fn: (r) => ({ r with _value: r._value / 1000000000.0 }))'
            '  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")'
            '  |> rename(columns: {sent_bps_tcp: "TCP", sent_bps_udp: "UDP"})'
            '  |> yield(name: "bandwidth")'
        )
    },
    'transfer': {
        'influxdb2': (
            'from(bucket: "mybucket")'
            '  |> range(start: {time}, stop: {end_date})'
            '  |> filter(fn: (r) => r._measurement == "{measurement}")'
            '  |> filter(fn: (r) => r._field == "sent_bytes_tcp" or r._field == "sent_bytes_udp")'
            '  |> filter(fn: (r) => r.content_type == "{content_type}")'
            '  |> filter(fn: (r) => r.object_id == "{object_id}")'
            '  |> sum()'
            '  |> map(fn: (r) => ({ r with _value: r._value / 1000000000.0 }))'
            '  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")'
            '  |> rename(columns: {sent_bytes_tcp: "TCP", sent_bytes_udp: "UDP"})'
            '  |> yield(name: "transfer")'
        )
    },
    'retransmits': {
        'influxdb2': (
            'from(bucket: "mybucket")'
            '  |> range(start: {time}, stop: {end_date})'
            '  |> filter(fn: (r) => r._measurement == "{measurement}")'
            '  |> filter(fn: (r) => r._field == "retransmits")'
            '  |> filter(fn: (r) => r.content_type == "{content_type}")'
            '  |> filter(fn: (r) => r.object_id == "{object_id}")'
            '  |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)'
            '  |> yield(name: "retransmits")'
        )
    },
    'jitter': {
        'influxdb2': (
            'from(bucket: "mybucket")'
            '  |> range(start: {time}, stop: {end_date})'
            '  |> filter(fn: (r) => r._measurement == "{measurement}")'
            '  |> filter(fn: (r) => r._field == "jitter")'
            '  |> filter(fn: (r) => r.content_type == "{content_type}")'
            '  |> filter(fn: (r) => r.object_id == "{object_id}")'
            '  |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)'
            '  |> yield(name: "jitter")'
        )
    },
    'datagram': {
        'influxdb2': (
            'from(bucket: "mybucket")'
            '  |> range(start: {time}, stop: {end_date})'
            '  |> filter(fn: (r) => r._measurement == "{measurement}")'
            '  |> filter(fn: (r) => r._field == "lost_packets" or r._field == "total_packets")'
            '  |> filter(fn: (r) => r.content_type == "{content_type}")'
            '  |> filter(fn: (r) => r.object_id == "{object_id}")'
            '  |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)'
            '  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")'
            '  |> rename(columns: {lost_packets: "lost_datagram", total_packets: "total_datagram"})'
            '  |> yield(name: "datagram")'
        )
    },
    'datagram_loss': {
        'influxdb2': (
            'from(bucket: "mybucket")'
            '  |> range(start: {time}, stop: {end_date})'
            '  |> filter(fn: (r) => r._measurement == "{measurement}")'
            '  |> filter(fn: (r) => r._field == "lost_percent")'
            '  |> filter(fn: (r) => r.content_type == "{content_type}")'
            '  |> filter(fn: (r) => r.object_id == "{object_id}")'
            '  |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)'
            '  |> yield(name: "datagram_loss")'
        )
    }
}
