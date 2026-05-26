"""
InfluxDB 2.x Flux queries for monitoring charts.
These queries follow the Flux query language syntax.
"""

from openwisp_monitoring.db.backends.influxdb.queries import (
    chart_query as v1_chart_query,
)

_default_flux_query = (
    'from(bucket: "{bucket}")'
    " |> range(start: {time_start})"
    ' |> filter(fn: (r) => r._measurement == "{key}")'
)

chart_query = {
    chart_type: {"influxdb2": _default_flux_query} for chart_type in v1_chart_query
}

chart_query.update(
    {
        "uptime": {
            "influxdb2": (
                'from(bucket: "{bucket}")'
                " |> range(start: {time_start})"
                ' |> filter(fn: (r) => r._measurement == "{key}")'
                ' |> filter(fn: (r) => r.content_type == "{content_type}")'
                ' |> filter(fn: (r) => r.object_id == "{object_id}")'
                ' |> filter(fn: (r) => r._field == "{field_name}")'
                " |> aggregateWindow(every: 1d, fn: mean)"
                " |> map(fn: (r) => ({{r with _value: r._value * 100}}))"
            )
        },
        "packet_loss": {
            "influxdb2": (
                'from(bucket: "{bucket}")'
                " |> range(start: {time_start})"
                ' |> filter(fn: (r) => r._measurement == "{key}")'
                ' |> filter(fn: (r) => r.content_type == "{content_type}")'
                ' |> filter(fn: (r) => r.object_id == "{object_id}")'
                ' |> filter(fn: (r) => r._field == "loss")'
                " |> aggregateWindow(every: 1d, fn: mean)"
            )
        },
        "rtt": {
            "influxdb2": (
                'from(bucket: "{bucket}")'
                " |> range(start: {time_start})"
                ' |> filter(fn: (r) => r._measurement == "{key}")'
                ' |> filter(fn: (r) => r.content_type == "{content_type}")'
                ' |> filter(fn: (r) => r.object_id == "{object_id}")'
                " |> filter(fn: (r) => r._field =~ /^rtt_(avg|max|min)$/)"
                " |> aggregateWindow(every: 1d, fn: mean)"
            )
        },
        "wifi_clients": {
            "influxdb2": (
                'from(bucket: "{bucket}")'
                " |> range(start: {time_start})"
                ' |> filter(fn: (r) => r._measurement == "{key}")'
                ' |> filter(fn: (r) => r.content_type == "{content_type}")'
                ' |> filter(fn: (r) => r.object_id == "{object_id}")'
                ' |> filter(fn: (r) => r.ifname == "{ifname}")'
                ' |> filter(fn: (r) => r._field == "{field_name}")'
                " |> aggregateWindow(every: 1d, fn: count)"
            )
        },
        "traffic": {
            "influxdb2": (
                'from(bucket: "{bucket}")'
                " |> range(start: {time_start})"
                ' |> filter(fn: (r) => r._measurement == "{key}")'
                ' |> filter(fn: (r) => r.content_type == "{content_type}")'
                ' |> filter(fn: (r) => r.object_id == "{object_id}")'
                ' |> filter(fn: (r) => r.ifname == "{ifname}")'
                " |> filter(fn: (r) => r._field =~ /^(tx_bytes|rx_bytes)$/)"
                " |> aggregateWindow(every: 1d, fn: sum)"
            )
        },
    }
)

field_mappings = {
    "uptime": "uptime",
    "packet_loss": "loss",
    "rtt": "rtt_avg",
    "traffic": ["tx_bytes", "rx_bytes"],
    "wifi_clients": "num_clients",
}

default_chart_query = [_default_flux_query, ""]

device_data_query = (
    'from(bucket: "{0}") |> range(start: -24h) '
    '|> filter(fn: (r) => r._measurement == "{1}" and r.pk == "{2}") '
    "|> last()"
)
