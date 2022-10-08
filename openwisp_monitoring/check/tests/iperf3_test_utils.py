# flake8: noqa

RESULT_TCP = """
{
  "start": {
    "connected": [
      {
        "socket": 5,
        "local_host": "127.0.0.1",
        "local_port": 54966,
        "remote_host": "127.0.0.1",
        "remote_port": 5201
      }
    ],
    "version": "iperf 3.9",
    "system_info": "Linux openwisp-desktop 5.11.2-51-generic #58~20.04.1-Ubuntu SMP Tue Jun 14 11:29:12 UTC 2022 x86_64",
    "timestamp": {
      "time": "Thu, 30 Jun 2022 21:39:55 GMT",
      "timesecs": 1656625195
    },
    "connecting_to": {
      "host": "localhost",
      "port": 5201
    },
    "cookie": "npx4ad65t3j4wginxr4a7mqedmkhhspx3sob",
    "tcp_mss_default": 32768,
    "sock_bufsize": 0,
    "sndbuf_actual": 16384,
    "rcvbuf_actual": 131072,
    "test_start": {
      "protocol": "TCP",
      "num_streams": 1,
      "blksize": 131072,
      "omit": 0,
      "duration": 10,
      "bytes": 0,
      "blocks": 0,
      "reverse": 0,
      "tos": 0
    }
  },
  "intervals": [
    {
      "streams": [
        {
          "socket": 5,
          "start": 0,
          "end": 1.000048,
          "seconds": 1.000048041343689,
          "bytes": 5790760960,
          "bits_per_second": 46323862219.414116,
          "retransmits": 0,
          "snd_cwnd": 1506109,
          "rtt": 22,
          "rttvar": 3,
          "pmtu": 65535,
          "omitted": false,
          "sender": true
        }
      ],
      "sum": {
        "start": 0,
        "end": 1.000048,
        "seconds": 1.000048041343689,
        "bytes": 5790760960,
        "bits_per_second": 46323862219.414116,
        "retransmits": 0,
        "omitted": false,
        "sender": true
      }
    },
    {
      "streams": [
        {
          "socket": 5,
          "start": 1.000048,
          "end": 2.000185,
          "seconds": 1.0001369714736938,
          "bytes": 5463080960,
          "bits_per_second": 43698662209.83867,
          "retransmits": 0,
          "snd_cwnd": 2160939,
          "rtt": 22,
          "rttvar": 3,
          "pmtu": 65535,
          "omitted": false,
          "sender": true
        }
      ],
      "sum": {
        "start": 1.000048,
        "end": 2.000185,
        "seconds": 1.0001369714736938,
        "bytes": 5463080960,
        "bits_per_second": 43698662209.83867,
        "retransmits": 0,
        "omitted": false,
        "sender": true
      }
    },
    {
      "streams": [
        {
          "socket": 5,
          "start": 2.000185,
          "end": 3.00019,
          "seconds": 1.0000050067901611,
          "bytes": 5679349760,
          "bits_per_second": 45434570598.638954,
          "retransmits": 0,
          "snd_cwnd": 2553837,
          "rtt": 21,
          "rttvar": 1,
          "pmtu": 65535,
          "omitted": false,
          "sender": true
        }
      ],
      "sum": {
        "start": 2.000185,
        "end": 3.00019,
        "seconds": 1.0000050067901611,
        "bytes": 5679349760,
        "bits_per_second": 45434570598.638954,
        "retransmits": 0,
        "omitted": false,
        "sender": true
      }
    },
    {
      "streams": [
        {
          "socket": 5,
          "start": 3.00019,
          "end": 4.000232,
          "seconds": 1.0000419616699219,
          "bytes": 5710807040,
          "bits_per_second": 45684539320.4405,
          "retransmits": 0,
          "snd_cwnd": 2553837,
          "rtt": 24,
          "rttvar": 5,
          "pmtu": 65535,
          "omitted": false,
          "sender": true
        }
      ],
      "sum": {
        "start": 3.00019,
        "end": 4.000232,
        "seconds": 1.0000419616699219,
        "bytes": 5710807040,
        "bits_per_second": 45684539320.4405,
        "retransmits": 0,
        "omitted": false,
        "sender": true
      }
    },
    {
      "streams": [
        {
          "socket": 5,
          "start": 4.000232,
          "end": 5.000158,
          "seconds": 0.999925971031189,
          "bytes": 5307105280,
          "bits_per_second": 42459985508.942955,
          "retransmits": 0,
          "snd_cwnd": 3208667,
          "rtt": 27,
          "rttvar": 4,
          "pmtu": 65535,
          "omitted": false,
          "sender": true
        }
      ],
      "sum": {
        "start": 4.000232,
        "end": 5.000158,
        "seconds": 0.999925971031189,
        "bytes": 5307105280,
        "bits_per_second": 42459985508.942955,
        "retransmits": 0,
        "omitted": false,
        "sender": true
      }
    },
    {
      "streams": [
        {
          "socket": 5,
          "start": 5.000158,
          "end": 6.000229,
          "seconds": 1.0000710487365723,
          "bytes": 5308416000,
          "bits_per_second": 42464310964.35657,
          "retransmits": 0,
          "snd_cwnd": 3208667,
          "rtt": 28,
          "rttvar": 1,
          "pmtu": 65535,
          "omitted": false,
          "sender": true
        }
      ],
      "sum": {
        "start": 5.000158,
        "end": 6.000229,
        "seconds": 1.0000710487365723,
        "bytes": 5308416000,
        "bits_per_second": 42464310964.35657,
        "retransmits": 0,
        "omitted": false,
        "sender": true
      }
    },
    {
      "streams": [
        {
          "socket": 5,
          "start": 6.000229,
          "end": 7.000056,
          "seconds": 0.9998270273208618,
          "bytes": 5241569280,
          "bits_per_second": 41939808681.0701,
          "retransmits": 0,
          "snd_cwnd": 3208667,
          "rtt": 23,
          "rttvar": 4,
          "pmtu": 65535,
          "omitted": false,
          "sender": true
        }
      ],
      "sum": {
        "start": 6.000229,
        "end": 7.000056,
        "seconds": 0.9998270273208618,
        "bytes": 5241569280,
        "bits_per_second": 41939808681.0701,
        "retransmits": 0,
        "omitted": false,
        "sender": true
      }
    },
    {
      "streams": [
        {
          "socket": 5,
          "start": 7.000056,
          "end": 8.000202,
          "seconds": 1.0001460313797,
          "bytes": 5734400000,
          "bits_per_second": 45868501759.40331,
          "retransmits": 0,
          "snd_cwnd": 3208667,
          "rtt": 22,
          "rttvar": 1,
          "pmtu": 65535,
          "omitted": false,
          "sender": true
        }
      ],
      "sum": {
        "start": 7.000056,
        "end": 8.000202,
        "seconds": 1.0001460313797,
        "bytes": 5734400000,
        "bits_per_second": 45868501759.40331,
        "retransmits": 0,
        "omitted": false,
        "sender": true
      }
    },
    {
      "streams": [
        {
          "socket": 5,
          "start": 8.000202,
          "end": 9.0003,
          "seconds": 1.0000979900360107,
          "bytes": 5415895040,
          "bits_per_second": 43322915105.98867,
          "retransmits": 0,
          "snd_cwnd": 3208667,
          "rtt": 35,
          "rttvar": 12,
          "pmtu": 65535,
          "omitted": false,
          "sender": true
        }
      ],
      "sum": {
        "start": 8.000202,
        "end": 9.0003,
        "seconds": 1.0000979900360107,
        "bytes": 5415895040,
        "bits_per_second": 43322915105.98867,
        "retransmits": 0,
        "omitted": false,
        "sender": true
      }
    },
    {
      "streams": [
        {
          "socket": 5,
          "start": 9.0003,
          "end": 10.000218,
          "seconds": 0.999917984008789,
          "bytes": 5402787840,
          "bits_per_second": 43225847930.76398,
          "retransmits": 0,
          "snd_cwnd": 3208667,
          "rtt": 26,
          "rttvar": 17,
          "pmtu": 65535,
          "omitted": false,
          "sender": true
        }
      ],
      "sum": {
        "start": 9.0003,
        "end": 10.000218,
        "seconds": 0.999917984008789,
        "bytes": 5402787840,
        "bits_per_second": 43225847930.76398,
        "retransmits": 0,
        "omitted": false,
        "sender": true
      }
    }
  ],
  "end": {
    "streams": [
      {
        "sender": {
          "socket": 5,
          "start": 0,
          "end": 10.000218,
          "seconds": 10.000218,
          "bytes": 55054172160,
          "bits_per_second": 44042377604.16823,
          "retransmits": 0,
          "max_snd_cwnd": 3208667,
          "max_rtt": 35,
          "min_rtt": 21,
          "mean_rtt": 25,
          "sender": true
        },
        "receiver": {
          "socket": 5,
          "start": 0,
          "end": 10.000272,
          "seconds": 10.000218,
          "bytes": 55054172160,
          "bits_per_second": 44042139781.797935,
          "sender": true
        }
      }
    ],
    "sum_sent": {
      "start": 0,
      "end": 10.000218,
      "seconds": 10.000218,
      "bytes": 55054172160,
      "bits_per_second": 44042377604.16823,
      "retransmits": 0,
      "sender": true
    },
    "sum_received": {
      "start": 0,
      "end": 10.000272,
      "seconds": 10.000272,
      "bytes": 55054172160,
      "bits_per_second": 44042139781.797935,
      "sender": true
    },
    "cpu_utilization_percent": {
      "host_total": 99.49882081069975,
      "host_user": 0.6620490539150914,
      "host_system": 98.83676176238454,
      "remote_total": 0.377797593572381,
      "remote_user": 0.02174276147834767,
      "remote_system": 0.35605477540538377
    },
    "sender_tcp_congestion": "cubic",
    "receiver_tcp_congestion": "cubic"
  }
}
"""

RESULT_UDP = """
{
    "start": {
        "connected": [
            {
                "socket": 5,
                "local_host": "127.0.0.1",
                "local_port": 54477,
                "remote_host": "127.0.0.1",
                "remote_port": 5201
            }
        ],
        "version": "iperf 3.9",
        "system_info": "openwisp-desktop 5.11.2-51-generic #58~20.04.1-Ubuntu SMP Tue Jun 14 11:29:12 UTC 2022 x86_64",
        "timestamp": {
            "time": "Thu, 30 Jun 2022 21:10:31 GMT",
            "timesecs": 1656623431
        },
        "connecting_to": {
            "host": "localhost",
            "port": 5201
        },
        "cookie": "kvuxkz3ncutquvpl2evufmdkn726molzocot",
        "sock_bufsize": 0,
        "sndbuf_actual": 212992,
        "rcvbuf_actual": 212992,
        "test_start": {
            "protocol": "UDP",
            "num_streams": 1,
            "blksize": 32768,
            "omit": 0,
            "duration": 10,
            "bytes": 0,
            "blocks": 0,
            "reverse": 0,
            "tos": 0
        }
    },
    "intervals": [
        {
            "streams": [
                {
                    "socket": 5,
                    "start": 0,
                    "end": 1.000057,
                    "seconds": 1.0000569820404053,
                    "bytes": 131072,
                    "bits_per_second": 1048516.253404483,
                    "packets": 4,
                    "omitted": false,
                    "sender": true
                }
            ],
            "sum": {
                "start": 0,
                "end": 1.000057,
                "seconds": 1.0000569820404053,
                "bytes": 131072,
                "bits_per_second": 1048516.253404483,
                "packets": 4,
                "omitted": false,
                "sender": true
            }
        },
        {
            "streams": [
                {
                    "socket": 5,
                    "start": 1.000057,
                    "end": 2.000079,
                    "seconds": 1.000022053718567,
                    "bytes": 131072,
                    "bits_per_second": 1048552.875509981,
                    "packets": 4,
                    "omitted": false,
                    "sender": true
                }
            ],
            "sum": {
                "start": 1.000057,
                "end": 2.000079,
                "seconds": 1.000022053718567,
                "bytes": 131072,
                "bits_per_second": 1048552.875509981,
                "packets": 4,
                "omitted": false,
                "sender": true
            }
        },
        {
            "streams": [
                {
                    "socket": 5,
                    "start": 2.000079,
                    "end": 3.000079,
                    "seconds": 1,
                    "bytes": 131072,
                    "bits_per_second": 1048576,
                    "packets": 4,
                    "omitted": false,
                    "sender": true
                }
            ],
            "sum": {
                "start": 2.000079,
                "end": 3.000079,
                "seconds": 1,
                "bytes": 131072,
                "bits_per_second": 1048576,
                "packets": 4,
                "omitted": false,
                "sender": true
            }
        },
        {
            "streams": [
                {
                    "socket": 5,
                    "start": 3.000079,
                    "end": 4.000079,
                    "seconds": 1,
                    "bytes": 131072,
                    "bits_per_second": 1048576,
                    "packets": 4,
                    "omitted": false,
                    "sender": true
                }
            ],
            "sum": {
                "start": 3.000079,
                "end": 4.000079,
                "seconds": 1,
                "bytes": 131072,
                "bits_per_second": 1048576,
                "packets": 4,
                "omitted": false,
                "sender": true
            }
        },
        {
            "streams": [
                {
                    "socket": 5,
                    "start": 4.000079,
                    "end": 5.000182,
                    "seconds": 1.0001029968261719,
                    "bytes": 131072,
                    "bits_per_second": 1048468.0111225117,
                    "packets": 4,
                    "omitted": false,
                    "sender": true
                }
            ],
            "sum": {
                "start": 4.000079,
                "end": 5.000182,
                "seconds": 1.0001029968261719,
                "bytes": 131072,
                "bits_per_second": 1048468.0111225117,
                "packets": 4,
                "omitted": false,
                "sender": true
            }
        },
        {
            "streams": [
                {
                    "socket": 5,
                    "start": 5.000182,
                    "end": 6.000056,
                    "seconds": 0.9998739957809448,
                    "bytes": 131072,
                    "bits_per_second": 1048708.1416504055,
                    "packets": 4,
                    "omitted": false,
                    "sender": true
                }
            ],
            "sum": {
                "start": 5.000182,
                "end": 6.000056,
                "seconds": 0.9998739957809448,
                "bytes": 131072,
                "bits_per_second": 1048708.1416504055,
                "packets": 4,
                "omitted": false,
                "sender": true
            }
        },
        {
            "streams": [
                {
                    "socket": 5,
                    "start": 6.000056,
                    "end": 7.000056,
                    "seconds": 1,
                    "bytes": 131072,
                    "bits_per_second": 1048576,
                    "packets": 4,
                    "omitted": false,
                    "sender": true
                }
            ],
            "sum": {
                "start": 6.000056,
                "end": 7.000056,
                "seconds": 1,
                "bytes": 131072,
                "bits_per_second": 1048576,
                "packets": 4,
                "omitted": false,
                "sender": true
            }
        },
        {
            "streams": [
                {
                    "socket": 5,
                    "start": 7.000056,
                    "end": 8.000056,
                    "seconds": 1,
                    "bytes": 131072,
                    "bits_per_second": 1048576,
                    "packets": 4,
                    "omitted": false,
                    "sender": true
                }
            ],
            "sum": {
                "start": 7.000056,
                "end": 8.000056,
                "seconds": 1,
                "bytes": 131072,
                "bits_per_second": 1048576,
                "packets": 4,
                "omitted": false,
                "sender": true
            }
        },
        {
            "streams": [
                {
                    "socket": 5,
                    "start": 8.000056,
                    "end": 9.000057,
                    "seconds": 1.0000009536743164,
                    "bytes": 131072,
                    "bits_per_second": 1048575.0000009537,
                    "packets": 4,
                    "omitted": false,
                    "sender": true
                }
            ],
            "sum": {
                "start": 8.000056,
                "end": 9.000057,
                "seconds": 1.0000009536743164,
                "bytes": 131072,
                "bits_per_second": 1048575.0000009537,
                "packets": 4,
                "omitted": false,
                "sender": true
            }
        },
        {
            "streams": [
                {
                    "socket": 5,
                    "start": 9.000057,
                    "end": 10.00006,
                    "seconds": 1.0000029802322388,
                    "bytes": 131072,
                    "bits_per_second": 1048572.8750093132,
                    "packets": 4,
                    "omitted": false,
                    "sender": true
                }
            ],
            "sum": {
                "start": 9.000057,
                "end": 10.00006,
                "seconds": 1.0000029802322388,
                "bytes": 131072,
                "bits_per_second": 1048572.8750093132,
                "packets": 4,
                "omitted": false,
                "sender": true
            }
        }
    ],
    "end": {
        "streams": [
            {
                "udp": {
                    "socket": 5,
                    "start": 0,
                    "end": 10.00006,
                    "seconds": 10.00006,
                    "bytes": 1310720,
                    "bits_per_second": 1048569.7085817485,
                    "jitter_ms": 0.011259258240784126,
                    "lost_packets": 0,
                    "packets": 40,
                    "lost_percent": 0,
                    "out_of_order": 0,
                    "sender": true
                }
            }
        ],
        "sum": {
            "start": 0,
            "end": 10.000115,
            "seconds": 10.000115,
            "bytes": 1310720,
            "bits_per_second": 1048569.7085817485,
            "jitter_ms": 0.011259258240784126,
            "lost_packets": 0,
            "packets": 40,
            "lost_percent": 0,
            "sender": true
        },
        "cpu_utilization_percent": {
            "host_total": 0.6057128493969417,
            "host_user": 0,
            "host_system": 0.6057128493969417,
            "remote_total": 0.016163250220207454,
            "remote_user": 0.01616789349806445,
            "remote_system": 0
        }
    }
}
"""

RESULT_FAIL = """
{
    "start": {
        "connected": [],
        "version": "iperf 3.7",
        "system_info": "Linux vm-openwrt 4.14.171 #0 SMP Thu Feb 27 21:05:12 2020 x86_64"
    },
    "intervals": [],
    "end": {},
    "error": "error - unable to connect to server: Connection refused"
}
"""
RESULT_AUTH_FAIL = """
{
    "start": {
        "connected": [],
        "version": "iperf 3.7",
        "system_info": "Linux vm-openwrt 4.14.171 #0 SMP Thu Feb 27 21:05:12 2020 x86_64",
        "timestamp": {
            "time": "Tue, 19 Jul 2022 12:23:38 UTC",
            "timesecs": 1658233418
        },
        "connecting_to": {
            "host": "192.168.5.109",
            "port": 5201
        },
        "cookie": "llz5f6akwyonbtcj3fx4phvfaflohdlvxr4z",
        "tcp_mss_default": 1460
    },
    "intervals": [],
    "end": {},
    "error": "error - test authorization failed"
}
"""
PARAM_ERROR = """Usage: iperf3 [-s|-c host] [options]
       iperf3 [-h|--help] [-v|--version]

Server or Client:
  -p, --port      #         server port to listen on/connect to
  -f, --format   [kmgtKMGT] format to report: Kbits, Mbits, Gbits, Tbits
  -i, --interval  #         seconds between periodic throughput reports
  -F, --file name           xmit/recv the specified file
  -A, --affinity n/n,m      set CPU affinity
  -B, --bind      <host>    bind to the interface associated with the address <host>
  -V, --verbose             more detailed output
  -J, --json                output in JSON format
  --logfile f               send output to a log file
  --forceflush              force flushing output at every interval
  -d, --debug               emit debugging output
  -v, --version             show version information and quit
  -h, --help                show this message and quit
Server specific:
  -s, --server              run in server mode
  -D, --daemon              run the server as a daemon
  -I, --pidfile file        write PID file
  -1, --one-off             handle one client connection then exit
  --rsa-private-key-path    path to the RSA private key used to decrypt
                            authentication credentials
  --authorized-users-path   path to the configuration file containing user
                            credentials
Client specific:
  -c, --client    <host>    run in client mode, connecting to <host>
  -u, --udp                 use UDP rather than TCP
  --connect-timeout #       timeout for control connection setup (ms)
  -b, --bitrate #[KMG][/#]  target bitrate in bits/sec (0 for unlimited)
                            (default 1 Mbit/sec for UDP, unlimited for TCP)
                            (optional slash and packet count for burst mode)
  --pacing-timer #[KMG]     set the timing for pacing, in microseconds (default 1000)
  --fq-rate #[KMG]          enable fair-queuing based socket pacing in
                            bits/sec (Linux only)
  -t, --time      #         time in seconds to transmit for (default 10 secs)
  -n, --bytes     #[KMG]    number of bytes to transmit (instead of -t)
  -k, --blockcount #[KMG]   number of blocks (packets) to transmit (instead of -t or -n)
  -l, --length    #[KMG]    length of buffer to read or write
                            (default 128 KB for TCP, dynamic or 1460 for UDP)
  --cport         <port>    bind to a specific client port (TCP and UDP, default: ephemeral port)
  -P, --parallel  #         number of parallel client streams to run
  -R, --reverse             run in reverse mode (server sends, client receives)
  --bidir                   run in bidirectional mode.
                            Client and server send and receive data.
  -w, --window    #[KMG]    set window size / socket buffer size
  -C, --congestion <algo>   set TCP congestion control algorithm (Linux and FreeBSD only)
  -M, --set-mss   #         set TCP/SCTP maximum segment size (MTU - 40 bytes)
  -N, --no-delay            set TCP/SCTP no delay, disabling Nagle's Algorithm
  -4, --version4            only use IPv4
  -6, --version6            only use IPv6
  -S, --tos N               set the IP type of service, 0-255.
                            The usual prefixes for octal and hex can be used,
                            i.e. 52, 064 and 0x34 all specify the same value.
  --dscp N or --dscp val    set the IP dscp value, either 0-63 or symbolic.
                            Numeric values can be specified in decimal,
                            octal and hex (see --tos above).
  -L, --flowlabel N         set the IPv6 flow label (only supported on Linux)
  -Z, --zerocopy            use a 'zero copy' method of sending data
  -O, --omit N              omit the first n seconds
  -T, --title str           prefix every output line with this string
  --extra-data str          data string to include in client and server JSON
  --get-server-output       get results from server
  --udp-counters-64bit      use 64-bit counters in UDP test packets
  --repeating-payload       use repeating pattern in payload, instead of
                            randomized payload (like in iperf2)
  --username                username for authentication
  --rsa-public-key-path     path to the RSA public key used to encrypt
                            authentication credentials

[KMG] indicates options that support a K/M/G suffix for kilo-, mega-, or giga-

iperf3 homepage at: https://software.es.net/iperf/
Report bugs to:     https://github.com/esnet/iperf
iperf3: parameter error - you must specify username (max 20 chars), password (max 20 chars) and a path to a valid public rsa client to be used"""

TEST_RSA_KEY = """MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAwuEm+iYrfSWJOupy6X3N
dxZvUCxvmoL3uoGAs0O0Y32unUQrwcTIxudy38JSuCccD+k2Rf8S4WuZSiTxaoea
6Du99YQGVZeY67uJ21SWFqWU+w6ONUj3TrNNWoICN7BXGLE2BbSBz9YaXefE3aqw
GhEjQz364Itwm425vHn2MntSp0weWb4hUCjQUyyooRXPrFUGBOuY+VvAvMyAG4Uk
msapnWnBSxXt7Tbb++A5XbOMdM2mwNYDEtkD5ksC/x3EVBrI9FvENsH9+u/8J9Mf
2oPl4MnlCMY86MQypkeUn7eVWfDnseNky7TyC0/IgCXve/iaydCCFdkjyo1MTAA4
BQIDAQAB"""

INVALID_PARAMS = [
    {'host': ''},
    {'host': 12},
    {'host': 'test.openwisp.io'},
    {'username': 121},
    {'password': -323},
    {'rsa_public_key': 1334},
    {'username': ''},
    {'password': 0},
    {'rsa_public_key': 0},
    {
        'username': 'openwisp-test-user',
        'password': 'open-pass',
        'rsa_public_key': -1,
    },
    {
        'username': 1123,
        'password': 'rossi',
        'rsa_public_key': '',
    },
    {
        'username': 'openwisp-test-user',
        'password': -214,
    },
    {
        'client_options': {
            'port': 'testport',
            'time': 120,
            'tcp': {'bitrate': '10M'},
            'udp': {'bitrate': '50M'},
        }
    },
    {
        'host': ['test.openwisp.io'],
        'client_options': {
            'port': 'testport',
            'time': 120,
            'tcp': {'bitrate': '10M'},
            'udp': {'bitrate': '50M'},
        },
    },
    {
        'host': ['test.openwisp.io'],
        'client_options': {
            'port': 70000,
            'time': 120,
            'tcp': {'bitrate': '10M'},
            'udp': {'bitrate': '50M'},
        },
    },
    {
        'host': ['test.openwisp.io'],
        'client_options': {
            'port': -21,
            'time': 120,
            'tcp': {'bitrate': '10M'},
            'udp': {'bitrate': '50M'},
        },
    },
    {
        'host': ['test.openwisp.io'],
        'client_options': {
            'port': 5201,
            'time': 1200000,
            'tcp': {'bitrate': '10M'},
            'udp': {'bitrate': '50M'},
        },
    },
    {
        'host': ['test.openwisp.io'],
        'client_options': {
            'port': 5201,
            'time': 20,
            'tcp': {'bitrate': 10},
            'udp': {'bitrate': '50M'},
        },
    },
    {
        'host': ['test.openwisp.io'],
        'client_options': {
            'port': 5201,
            'time': 120,
            'tcp': {'bitrate': '10M'},
            'udp': {'bitrate': 50},
        },
    },
    {
        'host': ['test.openwisp.io'],
        'client_options': {
            'port': 5201,
            'bytes': 20,
            'tcp': {'bitrate': '10M'},
            'udp': {'bitrate': 50},
        },
    },
    {
        'host': ['test.openwisp.io'],
        'client_options': {
            'port': 5201,
            'bytes': '',
            'tcp': {'bitrate': '10M'},
            'udp': {'bitrate': 50},
        },
    },
    {
        'host': ['test.openwisp.io'],
        'client_options': {
            'port': 5201,
            'bytes': -1,
            'tcp': {'bitrate': '10M'},
            'udp': {'bitrate': 50},
        },
    },
    {
        'host': ['test.openwisp.io'],
        'client_options': {
            'port': 5201,
            'connect_timeout': -1,
            'tcp': {'bitrate': '10M'},
            'udp': {'bitrate': 50},
        },
    },
    {
        'host': ['test.openwisp.io'],
        'client_options': {
            'port': 5201,
            'connect_timeout': '11000',
            'tcp': {'bitrate': '10M'},
            'udp': {'bitrate': 50},
        },
    },
    {
        'host': ['test.openwisp.io'],
        'client_options': {
            'port': 5201,
            'blockcount': -13,
            'tcp': {'bitrate': '10M'},
            'udp': {'bitrate': 50},
        },
    },
    {
        'host': ['test.openwisp.io'],
        'client_options': {
            'port': 5201,
            'blockcount': '',
            'tcp': {'bitrate': '10M'},
            'udp': {'bitrate': 50},
        },
    },
    {
        'host': ['test.openwisp.io'],
        'client_options': {
            'port': 5201,
            'tcp': {'bitrate': '10M', 'length': 112},
            'udp': {'bitrate': 50},
        },
    },
    {
        'host': ['test.openwisp.io'],
        'client_options': {
            'port': 5201,
            'connect_timeout': 2000000,
            'blockcount': '100K',
            'tcp': {'bitrate': '10M'},
            'udp': {'bitrate': 50, 'length': 9595},
        },
    },
    {
        'host': ['test.openwisp.io'],
        'client_options': {
            'port': 5201,
            'parallel': '12',
            'connect_timeout': 2000000,
            'blockcount': '100K',
            'tcp': {'bitrate': '10M'},
            'udp': {'bitrate': 50, 'length': 9595},
        },
    },
    {
        'host': ['test.openwisp.io'],
        'client_options': {
            'port': 5201,
            'parallel': 0,
            'connect_timeout': 2000000,
            'blockcount': '100K',
            'tcp': {'bitrate': '10M'},
            'udp': {'bitrate': 50, 'length': 9595},
        },
    },
    {
        'host': ['test.openwisp.io'],
        'client_options': {
            'port': 5201,
            'parallel': 250,
            'connect_timeout': 2000000,
            'blockcount': '100K',
            'tcp': {'bitrate': '10M'},
            'udp': {'bitrate': 50, 'length': 9595},
        },
    },
    {
        'host': ['test.openwisp.io'],
        'client_options': {
            'port': 5201,
            'bidirectional': True,
            'connect_timeout': 2000000,
            'blockcount': '100K',
            'tcp': {'bitrate': '10M'},
            'udp': {'bitrate': 50, 'length': 9595},
        },
    },
    {
        'host': ['test.openwisp.io'],
        'client_options': {
            'port': 5201,
            'reverse': False,
            'connect_timeout': 2000000,
            'blockcount': '100K',
            'tcp': {'bitrate': '10M'},
            'udp': {'bitrate': 50, 'length': 9595},
        },
    },
    {
        'host': ['test.openwisp.io'],
        'client_options': {
            'port': 5201,
            'window': 0,
            'connect_timeout': 2000000,
            'blockcount': '100K',
            'tcp': {'bitrate': '10M'},
            'udp': {'bitrate': 50, 'length': 9595},
        },
    },
]
