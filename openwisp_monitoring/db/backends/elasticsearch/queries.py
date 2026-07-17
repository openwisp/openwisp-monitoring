from copy import deepcopy


class ElasticsearchQuery(dict):
    def replace(self, old, new):
        query = deepcopy(self)

        def replace_value(value):
            if isinstance(value, str):
                return value.replace(old, new)
            if isinstance(value, dict):
                return {key: replace_value(item) for key, item in value.items()}
            if isinstance(value, list):
                return [replace_value(item) for item in value]
            return value

        return ElasticsearchQuery(replace_value(query))


class ElasticsearchDefaultChartQuery:
    def resolve(self, has_object_scope=False):
        filters = ["content_type", "object_id"] if has_object_scope else []
        return ElasticsearchQuery(
            {
                "__openwisp_query_type": "raw_chart",
                "aggregate": False,
                "field": "{field_name}",
                "filters": filters,
            }
        )


def _metric(name, field, agg="avg", scale=None, round_value=False):
    metric = {"name": name, "field": field, "agg": agg}
    if scale is not None:
        metric["scale"] = scale
    if round_value:
        metric["round"] = True
    return metric


def _chart(*metrics):
    return ElasticsearchQuery(
        {
            "__openwisp_query_type": "chart",
            "aggregate": True,
            "metrics": list(metrics),
        }
    )


_gb = 1 / 1000000000

chart_query = {
    "uptime": {
        "elasticsearch": _chart(
            _metric("uptime", "{field_name}", scale=100),
        )
    },
    "packet_loss": {
        "elasticsearch": _chart(
            _metric("packet_loss", "loss"),
        )
    },
    "rtt": {
        "elasticsearch": _chart(
            _metric("RTT_average", "rtt_avg"),
            _metric("RTT_max", "rtt_max"),
            _metric("RTT_min", "rtt_min"),
        )
    },
    "wifi_clients": {
        "elasticsearch": _chart(
            _metric("wifi_clients", "{field_name}", agg="cardinality"),
        )
    },
    "general_wifi_clients": {
        "elasticsearch": _chart(
            _metric("wifi_clients", "{field_name}", agg="cardinality"),
        )
    },
    "traffic": {
        "elasticsearch": _chart(
            _metric("upload", "tx_bytes", agg="sum", scale=_gb),
            _metric("download", "rx_bytes", agg="sum", scale=_gb),
        )
    },
    "general_traffic": {
        "elasticsearch": _chart(
            _metric("upload", "tx_bytes", agg="sum", scale=_gb),
            _metric("download", "rx_bytes", agg="sum", scale=_gb),
        )
    },
    "memory": {
        "elasticsearch": _chart(
            _metric("memory_usage", "percent_used"),
        )
    },
    "cpu": {
        "elasticsearch": _chart(
            _metric("CPU_load", "cpu_usage"),
        )
    },
    "disk": {
        "elasticsearch": _chart(
            _metric("disk_usage", "used_disk"),
        )
    },
    "signal_strength": {
        "elasticsearch": _chart(
            _metric("signal_strength", "signal_strength", round_value=True),
            _metric("signal_power", "signal_power", round_value=True),
        )
    },
    "signal_quality": {
        "elasticsearch": _chart(
            _metric("signal_quality", "signal_quality", round_value=True),
            _metric("signal_to_noise_ratio", "snr", round_value=True),
        )
    },
    "access_tech": {
        "elasticsearch": _chart(
            _metric("access_tech", "access_tech", agg="mode"),
        )
    },
    "bandwidth": {
        "elasticsearch": _chart(
            _metric("TCP", "sent_bps_tcp", scale=_gb),
            _metric("UDP", "sent_bps_udp", scale=_gb),
        )
    },
    "transfer": {
        "elasticsearch": _chart(
            _metric("TCP", "sent_bytes_tcp", agg="sum", scale=_gb),
            _metric("UDP", "sent_bytes_udp", agg="sum", scale=_gb),
        )
    },
    "retransmits": {
        "elasticsearch": _chart(
            _metric("retransmits", "retransmits"),
        )
    },
    "jitter": {
        "elasticsearch": _chart(
            _metric("jitter", "jitter"),
        )
    },
    "datagram": {
        "elasticsearch": _chart(
            _metric("lost_datagram", "lost_packets"),
            _metric("total_datagram", "total_packets"),
        )
    },
    "datagram_loss": {
        "elasticsearch": _chart(
            _metric("datagram_loss", "lost_percent"),
        )
    },
}

summary_query = {
    key: {"elasticsearch": value["elasticsearch"]} for key, value in chart_query.items()
}
default_chart_query = ElasticsearchDefaultChartQuery()
device_data_query = "elasticsearch-device-data-query"
