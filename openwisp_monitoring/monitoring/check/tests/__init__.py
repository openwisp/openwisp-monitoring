_FPING_REACHABLE = (
    '',
    bytes(
        '10.40.0.1 : xmt/rcv/%loss = 5/5/0%, min/avg/max = 0.04/0.08/0.15',
        encoding='utf8',
    ),
)

_FPING_UNREACHABLE = (
    '',
    bytes('192.168.255.255 : xmt/rcv/%loss = 3/0/100%', encoding='utf8'),
)
