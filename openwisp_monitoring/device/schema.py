# NetJSON DeviceMonitoring schema,
# https://github.com/netjson/netjson/blob/master/schema/device-monitoring.json
schema = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "object",
    "additionalProperties": True,
    "required": ["type"],
    "properties": {
        "type": {"type": "string", "enum": ["DeviceMonitoring"]},
        "general": {
            "type": "object",
            "title": "General",
            "additionalProperties": True,
            "properties": {
                "local_time": {"type": "integer"},
                "uptime": {"type": "integer"},
            },
        },
        "resources": {
            "type": "object",
            "title": "Resources",
            "additionalProperties": True,
            "properties": {
                "load": {
                    "type": "array",
                    "items": {"type": "number", "minItems": 3, "maxItems": 3},
                },
                "memory": {
                    "id": "memory",
                    "type": "object",
                    "properties": {
                        "total": {"type": "integer"},
                        "free": {"type": "integer"},
                        "buffered": {"type": "integer"},
                        "cache": {"type": "integer"},
                    },
                },
                "swap": {
                    "type": "object",
                    "properties": {
                        "total": {"type": "integer"},
                        "free": {"type": "integer"},
                    },
                },
                "connections": {
                    "type": "object",
                    "properties": {
                        "ipv4": {
                            "type": "object",
                            "properties": {
                                "tcp": {"type": "integer"},
                                "udp": {"type": "integer"},
                            },
                        },
                        "ipv6": {
                            "type": "object",
                            "properties": {
                                "tcp": {"type": "integer"},
                                "udp": {"type": "integer"},
                            },
                        },
                    },
                },
                "processes": {
                    "type": "object",
                    "properties": {
                        "running": {"type": "integer"},
                        "sleeping": {"type": "integer"},
                        "blocked": {"type": "integer"},
                        "zombie": {"type": "integer"},
                        "stopped": {"type": "integer"},
                        "paging": {"type": "integer"},
                    },
                },
                "cpu": {
                    "type": "object",
                    "properties": {
                        "frequency": {"type": "integer"},
                        "user": {"type": "integer"},
                        "system": {"type": "integer"},
                        "nice": {"type": "integer"},
                        "idle": {"type": "integer"},
                        "iowait": {"type": "integer"},
                        "irq": {"type": "integer"},
                        "softirq": {"type": "integer"},
                    },
                },
                "flash": {
                    "type": "object",
                    "properties": {
                        "total": {"type": "integer"},
                        "free": {"type": "integer"},
                    },
                },
                "storage": {
                    "type": "object",
                    "properties": {
                        "total": {"type": "integer"},
                        "free": {"type": "integer"},
                    },
                },
            },
        },
        "interfaces": {
            "type": "array",
            "title": "Interfaces",
            "uniqueItems": True,
            "additionalItems": True,
            "items": {
                "type": "object",
                "title": "Interface",
                "additionalProperties": True,
                "required": ["name"],
                "properties": {
                    "name": {"type": "string"},
                    "uptime": {"type": "integer"},
                    "statistics": {
                        "type": "object",
                        "properties": {
                            "collisions": {"type": "integer"},
                            "rx_frame_errors": {"type": "integer"},
                            "tx_compressed": {"type": "integer"},
                            "multicast": {"type": "integer"},
                            "rx_length_errors": {"type": "integer"},
                            "tx_dropped": {"type": "integer"},
                            "rx_bytes": {"type": "integer"},
                            "rx_missed_errors": {"type": "integer"},
                            "tx_errors": {"type": "integer"},
                            "rx_compressed": {"type": "integer"},
                            "rx_over_errors": {"type": "integer"},
                            "tx_fifo_errors": {"type": "integer"},
                            "rx_crc_errors": {"type": "integer"},
                            "rx_packets": {"type": "integer"},
                            "tx_heartbeat_errors": {"type": "integer"},
                            "rx_dropped": {"type": "integer"},
                            "tx_aborted_errors": {"type": "integer"},
                            "tx_packets": {"type": "integer"},
                            "rx_errors": {"type": "integer"},
                            "tx_bytes": {"type": "integer"},
                            "tx_window_errors": {"type": "integer"},
                            "rx_fifo_errors": {"type": "integer"},
                            "tx_carrier_errors": {"type": "integer"},
                        },
                    },
                },
            },
        },
    },
}
