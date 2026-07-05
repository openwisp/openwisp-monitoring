"""
InfluxDB 2.x Flux queries for monitoring charts.
"""

_range = (
    'import "date"\nfrom(bucket: "{bucket}")'
    " |> range(start: {time_start}{end_range})"
    ' |> filter(fn: (r) => r._measurement == "{key}")'
)

_object_filters = (
    "{content_type_filter}"
    "{object_id_filter}"
    "{ifname_filter}"
    "{organization_id_filter}"
    "{location_id_filter}"
    "{floorplan_id_filter}"
)


def _window(fn):
    return (
        f' |> aggregateWindow(every: {{window}}, fn: {fn}, timeSrc: "_start")'
        " |> map(fn: (r) => "
        "({{r with _time: date.truncate(t: r._time, unit: {window})}}))"
    )


_window_mean = _window("mean")
_window_sum = _window("sum")
_window_count = _window("count")
_window_mode = _window("mode")

_wifi_clients_query = (
    _range
    + _object_filters
    + ' |> filter(fn: (r) => r._field == "{field_name}")'
    + " |> window(every: {window}, createEmpty: true)"
    + ' |> unique(column: "_value")'
    + " |> count()"
    + ' |> duplicate(column: "_start", as: "_time")'
    + ' |> map(fn: (r) => ({{r with _field: "wifi_clients"}}))'
)

_traffic_query = (
    _range
    + _object_filters
    + " |> filter(fn: (r) => r._field =~ /^(tx_bytes|rx_bytes)$/)"
    + _window_sum
    + " |> map(fn: (r) => ({{r with "
    + '_field: if r._field == "tx_bytes" then "upload" else "download", '
    + "_value: float(v: r._value) / 1000000000.0}}))"
)

chart_query = {
    "uptime": {
        "influxdb2": (
            _range
            + _object_filters
            + ' |> filter(fn: (r) => r._field == "{field_name}")'
            + _window_mean
            + " |> map(fn: (r) => "
            + '({{r with _field: "uptime", _value: float(v: r._value) * 100.0}}))'
        )
    },
    "packet_loss": {
        "influxdb2": (
            _range
            + _object_filters
            + ' |> filter(fn: (r) => r._field == "loss")'
            + _window_mean
            + ' |> map(fn: (r) => ({{r with _field: "packet_loss"}}))'
        )
    },
    "rtt": {
        "influxdb2": (
            _range
            + _object_filters
            + " |> filter(fn: (r) => r._field =~ /^rtt_(avg|max|min)$/)"
            + _window_mean
            + " |> map(fn: (r) => ({{r with _field: "
            + 'if r._field == "rtt_avg" then "RTT_average" '
            + 'else if r._field == "rtt_max" then "RTT_max" '
            + 'else "RTT_min"}}))'
        )
    },
    "wifi_clients": {"influxdb2": _wifi_clients_query},
    "general_wifi_clients": {"influxdb2": _wifi_clients_query},
    "traffic": {"influxdb2": _traffic_query},
    "general_traffic": {"influxdb2": _traffic_query},
    "memory": {
        "influxdb2": (
            _range
            + _object_filters
            + ' |> filter(fn: (r) => r._field == "percent_used")'
            + _window_mean
            + ' |> map(fn: (r) => ({{r with _field: "memory_usage"}}))'
        )
    },
    "cpu": {
        "influxdb2": (
            _range
            + _object_filters
            + ' |> filter(fn: (r) => r._field == "cpu_usage")'
            + _window_mean
            + ' |> map(fn: (r) => ({{r with _field: "CPU_load"}}))'
        )
    },
    "disk": {
        "influxdb2": (
            _range
            + _object_filters
            + ' |> filter(fn: (r) => r._field == "used_disk")'
            + _window_mean
            + ' |> map(fn: (r) => ({{r with _field: "disk_usage"}}))'
        )
    },
    "signal_strength": {
        "influxdb2": (
            _range
            + _object_filters
            + " |> filter(fn: (r) => r._field =~ /^(signal_strength|signal_power)$/)"
            + _window_mean
            + " |> map(fn: (r) => ({{r with _value: "
            + "if r._value >= 0.0 "
            + "then float(v: int(v: r._value + 0.5)) "
            + "else float(v: int(v: r._value - 0.5))}}))"
        )
    },
    "signal_quality": {
        "influxdb2": (
            _range
            + _object_filters
            + " |> filter(fn: (r) => r._field =~ /^(signal_quality|snr)$/)"
            + _window_mean
            + " |> map(fn: (r) => ({{r with "
            + '_field: if r._field == "snr" then "signal_to_noise_ratio" '
            + 'else "signal_quality", '
            + "_value: if r._value >= 0.0 "
            + "then float(v: int(v: r._value + 0.5)) "
            + "else float(v: int(v: r._value - 0.5))}}))"
        )
    },
    "access_tech": {
        "influxdb2": (
            _range
            + _object_filters
            + ' |> filter(fn: (r) => r._field == "access_tech")'
            + _window_mode
        )
    },
    "bandwidth": {
        "influxdb2": (
            _range
            + _object_filters
            + " |> filter(fn: (r) => r._field =~ /^(sent_bps_tcp|sent_bps_udp)$/)"
            + _window_mean
            + " |> map(fn: (r) => ({{r with "
            + '_field: if r._field == "sent_bps_tcp" then "TCP" else "UDP", '
            + "_value: float(v: r._value) / 1000000000.0}}))"
        )
    },
    "transfer": {
        "influxdb2": (
            _range
            + _object_filters
            + " |> filter(fn: (r) => r._field =~ /^(sent_bytes_tcp|sent_bytes_udp)$/)"
            + _window_sum
            + " |> map(fn: (r) => ({{r with "
            + '_field: if r._field == "sent_bytes_tcp" then "TCP" else "UDP", '
            + "_value: float(v: r._value) / 1000000000.0}}))"
        )
    },
    "retransmits": {
        "influxdb2": (
            _range
            + _object_filters
            + ' |> filter(fn: (r) => r._field == "retransmits")'
            + _window_mean
        )
    },
    "jitter": {
        "influxdb2": (
            _range
            + _object_filters
            + ' |> filter(fn: (r) => r._field == "jitter")'
            + _window_mean
        )
    },
    "datagram": {
        "influxdb2": (
            _range
            + _object_filters
            + " |> filter(fn: (r) => r._field =~ /^(lost_packets|total_packets)$/)"
            + _window_mean
            + " |> map(fn: (r) => ({{r with _field: "
            + 'if r._field == "lost_packets" then "lost_datagram" '
            + 'else "total_datagram"}}))'
        )
    },
    "datagram_loss": {
        "influxdb2": (
            _range
            + _object_filters
            + ' |> filter(fn: (r) => r._field == "lost_percent")'
            + _window_mean
            + ' |> map(fn: (r) => ({{r with _field: "datagram_loss"}}))'
        )
    },
}

default_chart_query = [
    (_range + "{content_type_filter}" + "{object_id_filter}" + "{field_filter}"),
    "",
]


class DeviceDataQuery:
    def format(self, retention_policy, measurement, pk):
        from openwisp_monitoring.db import timeseries_db

        bucket = timeseries_db._get_bucket_name(retention_policy)
        return (
            f'from(bucket: "{bucket}") |> range(start: -24h) '
            f'|> filter(fn: (r) => r._measurement == "{measurement}" '
            f'and r.pk == "{pk}") '
            "|> last()"
        )


device_data_query = DeviceDataQuery()
