chart_query = {
    'uptime': (
        "SELECT MEAN({field_name})*100 AS uptime FROM {key} WHERE "
        "time >= '{time}' AND content_type = '{content_type}' AND "
        "object_id = '{object_id}' GROUP BY time(1d)"
    ),
    'packet_loss': (
        "SELECT MEAN(loss) AS packet_loss FROM {key} WHERE "
        "time >= '{time}' AND content_type = '{content_type}' AND "
        "object_id = '{object_id}' GROUP BY time(1d)"
    ),
    'rtt': (
        "SELECT MEAN(rtt_avg) AS RTT_average, MEAN(rtt_max) AS "
        "RTT_max, MEAN(rtt_min) AS RTT_min FROM {key} WHERE "
        "time >= '{time}' AND content_type = '{content_type}' AND "
        "object_id = '{object_id}' GROUP BY time(1d)"
    ),
    'wifi_clients': (
        "SELECT COUNT(DISTINCT({field_name})) AS wifi_clients FROM {key} "
        "WHERE time >= '{time}' AND content_type = '{content_type}' "
        "AND object_id = '{object_id}' GROUP BY time(1d)"
    ),
    'traffic': (
        "SELECT SUM(tx_bytes) / 1000000000 AS upload, "
        "SUM(rx_bytes) / 1000000000 AS download FROM {key} "
        "WHERE time >= '{time}' AND content_type = '{content_type}' "
        "AND object_id = '{object_id}' GROUP BY time(1d)"
    ),
}

default_chart_query = [
    "SELECT {field_name} FROM {key} WHERE time >= '{time}'",
    " AND content_type = '{content_type}' AND object_id = '{object_id}'",
]

device_data_query = (
    "SELECT data FROM {0}.{1} WHERE pk = '{2}' " "ORDER BY time DESC LIMIT 1"
)
