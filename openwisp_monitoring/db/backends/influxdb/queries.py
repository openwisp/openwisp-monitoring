chart_query = {
    'uptime': {
        'influxdb': (
            "SELECT MEAN({field_name})*100 AS uptime FROM {key} WHERE "
            "time >= '{time}' AND content_type = '{content_type}' AND "
            "object_id = '{object_id}' GROUP BY time(1d)"
        )
    },
    'packet_loss': {
        'influxdb': (
            "SELECT MEAN(loss) AS packet_loss FROM {key} WHERE "
            "time >= '{time}' AND content_type = '{content_type}' AND "
            "object_id = '{object_id}' GROUP BY time(1d)"
        )
    },
    'rtt': {
        'influxdb': (
            "SELECT MEAN(rtt_avg) AS RTT_average, MEAN(rtt_max) AS "
            "RTT_max, MEAN(rtt_min) AS RTT_min FROM {key} WHERE "
            "time >= '{time}' AND content_type = '{content_type}' AND "
            "object_id = '{object_id}' GROUP BY time(1d)"
        )
    },
    'wifi_clients': {
        'influxdb': (
            "SELECT COUNT(DISTINCT({field_name})) AS wifi_clients FROM {key} "
            "WHERE time >= '{time}' AND content_type = '{content_type}' "
            "AND object_id = '{object_id}' GROUP BY time(1d)"
        )
    },
    'traffic': {
        'influxdb': (
            "SELECT SUM(tx_bytes) / 1000000000 AS upload, "
            "SUM(rx_bytes) / 1000000000 AS download FROM {key} "
            "WHERE time >= '{time}' AND content_type = '{content_type}' "
            "AND object_id = '{object_id}' GROUP BY time(1d)"
        )
    },
    'memory': {
        'influxdb': (
            "SELECT MEAN(percent_used) AS memory_usage "
            "FROM {key} WHERE time >= '{time}' AND content_type = '{content_type}' "
            "AND object_id = '{object_id}' GROUP BY time(1d)"
        )
    },
    'cpu': {
        'influxdb': (
            "SELECT MEAN(cpu_usage) AS CPU_load FROM {key} WHERE "
            "time >= '{time}' AND content_type = '{content_type}' AND "
            "object_id = '{object_id}' GROUP BY time(1d)"
        )
    },
    'disk': {
        'influxdb': (
            "SELECT MEAN(used_disk) AS disk_usage FROM {key} WHERE "
            "time >= '{time}' AND content_type = '{content_type}' AND "
            "object_id = '{object_id}' GROUP BY time(1d)"
        )
    },
    'signal_strength': {
        'influxdb': (
            "SELECT MEAN(signal_strength) AS signal_strength, "
            "MEAN(signal_power) AS signal_power FROM {key} WHERE "
            "time >= '{time}' AND content_type = '{content_type}' AND "
            "object_id = '{object_id}' GROUP BY time(1d)"
        )
    },
    'signal_quality': {
        'influxdb': (
            "SELECT MEAN(signal_quality) AS signal_quality, "
            "MEAN(snr) AS signal_to_noise_ratio FROM {key} WHERE "
            "time >= '{time}' AND content_type = '{content_type}' AND "
            "object_id = '{object_id}' GROUP BY time(1d)"
        )
    },
    'access_tech': {
        'influxdb': (
            "SELECT MODE(access_tech) AS access_tech FROM {key} WHERE "
            "time >= '{time}' AND content_type = '{content_type}' AND "
            "object_id = '{object_id}' GROUP BY time(1d)"
        )
    },
}

default_chart_query = [
    "SELECT {field_name} FROM {key} WHERE time >= '{time}'",
    " AND content_type = '{content_type}' AND object_id = '{object_id}'",
]

device_data_query = (
    "SELECT data FROM {0}.{1} WHERE pk = '{2}' " "ORDER BY time DESC LIMIT 1"
)
