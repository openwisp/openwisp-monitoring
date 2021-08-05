from collections import OrderedDict


class MockOpenWRT:
    def __init__(self, *args, **kwargs):
        pass

    def to_dict(self):
        res = OrderedDict(
            [
                ('type', 'DeviceMonitoring'),
                (
                    'general',
                    {
                        'hostname': '1C-3B-F3-10-0A-42',
                        'uptime': 3199,
                        'local_time': 1628255816,
                    },
                ),
                (
                    'resources',
                    OrderedDict(
                        [
                            ('load', [0.35, 0.19, 0.18]),
                            ('cpus', 1),
                            (
                                'memory',
                                {
                                    'total': 61452288,
                                    'shared': 106496,
                                    'free': 33239040,
                                    'cached': 8122368,
                                    'buffered': 2355200,
                                },
                            ),
                            ('swap', {'total': 0, 'free': 0}),
                        ]
                    ),
                ),
                (
                    'interfaces',
                    [
                        OrderedDict(
                            [
                                ('name', 'lo'),
                                (
                                    'statistics',
                                    {
                                        'mac': '',
                                        'type': 'loopback',
                                        'up': True,
                                        'rx_bytes': 17077,
                                        'tx_bytes': 17077,
                                        'mtu': 65536,
                                        'addresses': [
                                            {
                                                'family': 'ipv4',
                                                'address': '127.0.0.1',
                                                'mask': '255.0.0.0',
                                            }
                                        ],
                                    },
                                ),
                            ]
                        ),
                        OrderedDict(
                            [
                                ('name', 'eth0'),
                                (
                                    'statistics',
                                    {
                                        'mac': '1c:3b:c3:b3:10:0a',
                                        'type': 'ethernet',
                                        'up': True,
                                        'rx_bytes': 35260493,
                                        'tx_bytes': 1525254905,
                                        'mtu': 1500,
                                        'addresses': [],
                                    },
                                ),
                            ]
                        ),
                        OrderedDict(
                            [
                                ('name', 'Device 14c3:7662'),
                                (
                                    'statistics',
                                    {
                                        'mac': '',
                                        'type': 'wireless',
                                        'up': False,
                                        'rx_bytes': 0,
                                        'tx_bytes': 0,
                                        'mtu': 1500,
                                        'addresses': [],
                                    },
                                ),
                            ]
                        ),
                        OrderedDict(
                            [
                                ('name', 'br-lan'),
                                (
                                    'statistics',
                                    {
                                        'mac': '1c:3b:c3:b3:10:0a',
                                        'type': 'ethernet',
                                        'up': True,
                                        'rx_bytes': 30064879,
                                        'tx_bytes': 1513529004,
                                        'mtu': 1500,
                                        'addresses': [
                                            {
                                                'family': 'ipv4',
                                                'address': '192.168.1.1',
                                                'mask': '255.255.255.0',
                                            }
                                        ],
                                    },
                                ),
                            ]
                        ),
                        OrderedDict(
                            [
                                ('name', 'eth0.1'),
                                (
                                    'statistics',
                                    {
                                        'mac': '1c:3b:c3:b3:10:0a',
                                        'type': 'ethernet',
                                        'up': True,
                                        'rx_bytes': 30064879,
                                        'tx_bytes': 1518505434,
                                        'mtu': 1500,
                                        'addresses': [],
                                    },
                                ),
                            ]
                        ),
                        OrderedDict(
                            [
                                ('name', 'eth0.2'),
                                (
                                    'statistics',
                                    {
                                        'mac': '1c:3b:c3:b3:10:0a',
                                        'type': 'ethernet',
                                        'up': True,
                                        'rx_bytes': 0,
                                        'tx_bytes': 2169765,
                                        'mtu': 1500,
                                        'addresses': [],
                                    },
                                ),
                            ]
                        ),
                        OrderedDict(
                            [
                                ('name', 'wlan0'),
                                (
                                    'statistics',
                                    {
                                        'mac': '1c:3b:c3:b3:10:0a',
                                        'type': 'wireless',
                                        'up': True,
                                        'rx_bytes': 1522781779,
                                        'tx_bytes': 37676515,
                                        'mtu': 1500,
                                        'addresses': [
                                            {
                                                'family': 'ipv4',
                                                'address': '192.168.0.100',
                                                'mask': '255.255.255.0',
                                            }
                                        ],
                                    },
                                ),
                            ]
                        ),
                    ],
                ),
                (
                    'neighbors',
                    [
                        OrderedDict(
                            [
                                ('mac', '04:0e:3c:ca:55:5f'),
                                ('state', 'REACHABLE'),
                                ('interface', 'br-lan'),
                                ('ip', '192.168.1.140'),
                            ]
                        ),
                        OrderedDict(
                            [
                                ('mac', '04:0e:3c:ca:55:5f'),
                                ('state', 'STALE'),
                                ('interface', 'br-lan'),
                                ('ip', 'fe80::f02:1be3:6bf:967f'),
                            ]
                        ),
                        OrderedDict(
                            [
                                ('mac', '84:d8:1b:62:a3:55'),
                                ('state', 'DELAY'),
                                ('interface', 'wlan0'),
                                ('ip', '192.168.0.1'),
                            ]
                        ),
                        OrderedDict(
                            [
                                ('mac', 'ac:d5:64:1b:15:f7'),
                                ('state', 'STALE'),
                                ('interface', 'wlan0'),
                                ('ip', '192.168.0.105'),
                            ]
                        ),
                        OrderedDict(
                            [
                                ('mac', '52:e6:da:14:67:b0'),
                                ('state', 'STALE'),
                                ('interface', 'wlan0'),
                                ('ip', 'fe80::50e6:daff:fe14:67b0'),
                            ]
                        ),
                        OrderedDict(
                            [
                                ('mac', '0c:f3:46:87:25:17'),
                                ('state', 'STALE'),
                                ('interface', 'wlan0'),
                                ('ip', 'fe80::5137:b030:5cd6:c74c'),
                            ]
                        ),
                        OrderedDict(
                            [
                                ('mac', '70:3a:51:62:fb:9f'),
                                ('state', 'STALE'),
                                ('interface', 'wlan0'),
                                ('ip', 'fe80::a7ff:6d4b:7b4d:edc7'),
                            ]
                        ),
                        OrderedDict(
                            [
                                ('mac', 'aa:d1:28:7c:75:79'),
                                ('state', 'STALE'),
                                ('interface', 'wlan0'),
                                ('ip', 'fe80::a8d1:28ff:fe7c:7579'),
                            ]
                        ),
                        OrderedDict(
                            [
                                ('mac', '70:3a:51:62:fb:9f'),
                                ('state', 'STALE'),
                                ('interface', 'wlan0'),
                                ('ip', 'fe80::cbc1:e171:a82e:a21'),
                            ]
                        ),
                    ],
                ),
            ]
        )
        return res
