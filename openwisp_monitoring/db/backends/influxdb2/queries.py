"""
InfluxDB 2.x Flux queries for monitoring charts.
"""

_range = (
    'import "date"\n{timezone_import}from(bucket: "{bucket}")'
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

# Grouping strictly by _field merges data across different tag sets.
# This ensures aggregateWindow() processes all points together, even if
# Telegraf (or another writer) injects extra tags like 'host'.
# Without this, extra tags will split the data into multiple tables and
# cause charts to display partial or incorrect data.
_field_group = ' |> group(columns: ["_field"])'


def _window(fn):
    # {window_timezone} keeps daily and weekly Flux buckets aligned to the
    # request timezone.
    return (
        f"{_field_group} |> aggregateWindow(every: {{window}}, fn: {fn}, "
        'timeSrc: "_start"{window_timezone})'
        " |> map(fn: (r) => "
        "({{r with _time: date.truncate(t: r._time, "
        "unit: {window}{window_timezone})}}))"
    )


_window_mean = _window("mean")
_window_sum = _window("sum")
_window_count = _window("count")
# Mode is computed manually because count() overwrites _value with the
# occurrence count; mode_value keeps the original field value to restore later.
_window_mode = (
    _field_group
    + " |> window(every: {window}, createEmpty: false{window_timezone})"
    + ' |> duplicate(column: "_value", as: "mode_value")'
    + ' |> group(columns: ["_field", "_start", "_stop", "mode_value"])'
    + " |> count()"
    + ' |> group(columns: ["_field", "_start", "_stop"])'
    + ' |> sort(columns: ["_value"], desc: true)'
    + " |> limit(n: 1)"
    + " |> map(fn: (r) => "
    + "({{r with _value: r.mode_value, _time: date.truncate(t: r._start, "
    + "unit: {window}{window_timezone})}}))"
)
_summary_mean = _field_group + " |> mean()"
_summary_sum = _field_group + " |> sum()"
# Keep summary semantics aligned with InfluxDB 1 MODE(access_tech).
_summary_mode = (
    ' |> duplicate(column: "_value", as: "mode_value")'
    + ' |> group(columns: ["_field", "mode_value"])'
    + " |> count()"
    + ' |> group(columns: ["_field"])'
    + ' |> sort(columns: ["_value"], desc: true)'
    + " |> limit(n: 1)"
    + " |> map(fn: (r) => ({{r with _value: r.mode_value}}))"
)

_uptime_base = (
    _range + _object_filters + ' |> filter(fn: (r) => r._field == "{field_name}")'
)
_uptime_map = (
    " |> map(fn: (r) => "
    '({{r with _field: "uptime", _value: float(v: r._value) * 100.0}}))'
)

_packet_loss_base = (
    _range + _object_filters + ' |> filter(fn: (r) => r._field == "loss")'
)
_packet_loss_map = ' |> map(fn: (r) => ({{r with _field: "packet_loss"}}))'

_rtt_base = (
    _range
    + _object_filters
    + " |> filter(fn: (r) => r._field =~ /^rtt_(avg|max|min)$/)"
)
_rtt_map = (
    " |> map(fn: (r) => ({{r with _field: "
    + 'if r._field == "rtt_avg" then "RTT_average" '
    + 'else if r._field == "rtt_max" then "RTT_max" '
    + 'else "RTT_min"}}))'
)

_wifi_clients_base = (
    _range + _object_filters + ' |> filter(fn: (r) => r._field == "{field_name}")'
)
_wifi_clients_map = ' |> map(fn: (r) => ({{r with _field: "wifi_clients"}}))'
_wifi_clients_query = (
    _wifi_clients_base
    + _field_group
    + " |> window(every: {window}, createEmpty: true{window_timezone})"
    + ' |> unique(column: "_value")'
    + " |> count()"
    + ' |> duplicate(column: "_start", as: "_time")'
    + " |> map(fn: (r) => "
    + "({{r with _time: date.truncate(t: r._time, "
    + "unit: {window}{window_timezone})}}))"
    + _wifi_clients_map
)
_wifi_clients_summary_query = (
    _wifi_clients_base
    + _field_group
    + ' |> unique(column: "_value")'
    + " |> count()"
    + _wifi_clients_map
)

_traffic_base = (
    _range
    + _object_filters
    + " |> filter(fn: (r) => r._field =~ /^(tx_bytes|rx_bytes)$/)"
)
_traffic_map = (
    " |> map(fn: (r) => ({{r with "
    + '_field: if r._field == "tx_bytes" then "upload" else "download", '
    + "_value: float(v: r._value) / 1000000000.0}}))"
)
_traffic_query = _traffic_base + _window_sum + _traffic_map
_traffic_summary_query = _traffic_base + _summary_sum + _traffic_map

_memory_base = (
    _range + _object_filters + ' |> filter(fn: (r) => r._field == "percent_used")'
)
_memory_map = ' |> map(fn: (r) => ({{r with _field: "memory_usage"}}))'

_cpu_base = _range + _object_filters + ' |> filter(fn: (r) => r._field == "cpu_usage")'
_cpu_map = ' |> map(fn: (r) => ({{r with _field: "CPU_load"}}))'

_disk_base = _range + _object_filters + ' |> filter(fn: (r) => r._field == "used_disk")'
_disk_map = ' |> map(fn: (r) => ({{r with _field: "disk_usage"}}))'

_signal_strength_base = (
    _range
    + _object_filters
    + " |> filter(fn: (r) => r._field =~ /^(signal_strength|signal_power)$/)"
)
_rounded_signal_map = (
    " |> map(fn: (r) => ({{r with _value: "
    + "if r._value >= 0.0 "
    + "then float(v: int(v: r._value + 0.5)) "
    + "else float(v: int(v: r._value - 0.5))}}))"
)

_signal_quality_base = (
    _range
    + _object_filters
    + " |> filter(fn: (r) => r._field =~ /^(signal_quality|snr)$/)"
)
_signal_quality_map = (
    " |> map(fn: (r) => ({{r with "
    + '_field: if r._field == "snr" then "signal_to_noise_ratio" '
    + 'else "signal_quality", '
    + "_value: if r._value >= 0.0 "
    + "then float(v: int(v: r._value + 0.5)) "
    + "else float(v: int(v: r._value - 0.5))}}))"
)

_access_tech_base = (
    _range + _object_filters + ' |> filter(fn: (r) => r._field == "access_tech")'
)

_bandwidth_base = (
    _range
    + _object_filters
    + " |> filter(fn: (r) => r._field =~ /^(sent_bps_tcp|sent_bps_udp)$/)"
)
_bandwidth_map = (
    " |> map(fn: (r) => ({{r with "
    + '_field: if r._field == "sent_bps_tcp" then "TCP" else "UDP", '
    + "_value: float(v: r._value) / 1000000000.0}}))"
)

_transfer_base = (
    _range
    + _object_filters
    + " |> filter(fn: (r) => r._field =~ /^(sent_bytes_tcp|sent_bytes_udp)$/)"
)
_transfer_map = (
    " |> map(fn: (r) => ({{r with "
    + '_field: if r._field == "sent_bytes_tcp" then "TCP" else "UDP", '
    + "_value: float(v: r._value) / 1000000000.0}}))"
)

_retransmits_base = (
    _range + _object_filters + ' |> filter(fn: (r) => r._field == "retransmits")'
)
_jitter_base = _range + _object_filters + ' |> filter(fn: (r) => r._field == "jitter")'

_datagram_base = (
    _range
    + _object_filters
    + " |> filter(fn: (r) => r._field =~ /^(lost_packets|total_packets)$/)"
)
_datagram_map = (
    " |> map(fn: (r) => ({{r with _field: "
    + 'if r._field == "lost_packets" then "lost_datagram" '
    + 'else "total_datagram"}}))'
)

_datagram_loss_base = (
    _range + _object_filters + ' |> filter(fn: (r) => r._field == "lost_percent")'
)
_datagram_loss_map = ' |> map(fn: (r) => ({{r with _field: "datagram_loss"}}))'

chart_query = {
    "uptime": {"influxdb2": _uptime_base + _window_mean + _uptime_map},
    "packet_loss": {"influxdb2": _packet_loss_base + _window_mean + _packet_loss_map},
    "rtt": {"influxdb2": _rtt_base + _window_mean + _rtt_map},
    "wifi_clients": {"influxdb2": _wifi_clients_query},
    "general_wifi_clients": {"influxdb2": _wifi_clients_query},
    "traffic": {"influxdb2": _traffic_query},
    "general_traffic": {"influxdb2": _traffic_query},
    "memory": {"influxdb2": _memory_base + _window_mean + _memory_map},
    "cpu": {"influxdb2": _cpu_base + _window_mean + _cpu_map},
    "disk": {"influxdb2": _disk_base + _window_mean + _disk_map},
    "signal_strength": {
        "influxdb2": _signal_strength_base + _window_mean + _rounded_signal_map
    },
    "signal_quality": {
        "influxdb2": _signal_quality_base + _window_mean + _signal_quality_map
    },
    "access_tech": {"influxdb2": _access_tech_base + _window_mode},
    "bandwidth": {"influxdb2": _bandwidth_base + _window_mean + _bandwidth_map},
    "transfer": {"influxdb2": _transfer_base + _window_sum + _transfer_map},
    "retransmits": {"influxdb2": _retransmits_base + _window_mean},
    "jitter": {"influxdb2": _jitter_base + _window_mean},
    "datagram": {"influxdb2": _datagram_base + _window_mean + _datagram_map},
    "datagram_loss": {
        "influxdb2": _datagram_loss_base + _window_mean + _datagram_loss_map
    },
}

summary_query = {
    "uptime": {"influxdb2": _uptime_base + _summary_mean + _uptime_map},
    "packet_loss": {"influxdb2": _packet_loss_base + _summary_mean + _packet_loss_map},
    "rtt": {"influxdb2": _rtt_base + _summary_mean + _rtt_map},
    "wifi_clients": {"influxdb2": _wifi_clients_summary_query},
    "general_wifi_clients": {"influxdb2": _wifi_clients_summary_query},
    "traffic": {"influxdb2": _traffic_summary_query},
    "general_traffic": {"influxdb2": _traffic_summary_query},
    "memory": {"influxdb2": _memory_base + _summary_mean + _memory_map},
    "cpu": {"influxdb2": _cpu_base + _summary_mean + _cpu_map},
    "disk": {"influxdb2": _disk_base + _summary_mean + _disk_map},
    "signal_strength": {
        "influxdb2": _signal_strength_base + _summary_mean + _rounded_signal_map
    },
    "signal_quality": {
        "influxdb2": _signal_quality_base + _summary_mean + _signal_quality_map
    },
    "access_tech": {"influxdb2": _access_tech_base + _summary_mode},
    "bandwidth": {"influxdb2": _bandwidth_base + _summary_mean + _bandwidth_map},
    "transfer": {"influxdb2": _transfer_base + _summary_sum + _transfer_map},
    "retransmits": {"influxdb2": _retransmits_base + _summary_mean},
    "jitter": {"influxdb2": _jitter_base + _summary_mean},
    "datagram": {"influxdb2": _datagram_base + _summary_mean + _datagram_map},
    "datagram_loss": {
        "influxdb2": _datagram_loss_base + _summary_mean + _datagram_loss_map
    },
}

default_chart_query = [
    (_range + "{content_type_filter}" + "{object_id_filter}" + "{field_filter}"),
    "",
]

device_data_query = (
    "from(bucket: {bucket}) |> range(start: -24h) "
    "|> filter(fn: (r) => r._measurement == {measurement} and r.pk == {pk}) "
    "|> last()"
)
