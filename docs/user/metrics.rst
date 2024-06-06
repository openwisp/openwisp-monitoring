Metrics
=======

.. _device_status:

Device Status
-------------

This metric stores the status of the device for viewing purposes.

.. figure:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/device-status-1.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/device-status-1.png
    :align: center

.. figure:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/device-status-2.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/device-status-2.png
    :align: center

.. figure:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/device-status-3.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/device-status-3.png
    :align: center

.. figure:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/device-status-4.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/device-status-4.png
    :align: center

.. _ping:

Ping
----

================== ==================================================
**measurement**:   ``ping``
**types**:         ``int`` (reachable and loss), ``float`` (rtt)
**fields**:        ``reachable``, ``loss``, ``rtt_min``, ``rtt_max``,
                   ``rtt_avg``
**configuration**: ``ping``
**charts**:        ``uptime``, ``packet_loss``, ``rtt``
================== ==================================================

**Uptime**:

.. figure:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/uptime.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/uptime.png
    :align: center

**Packet loss**:

.. figure:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/packet-loss.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/packet-loss.png
    :align: center

**Round Trip Time**:

.. figure:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/rtt.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/rtt.png
    :align: center

.. _traffic:

Traffic
-------

================== ==========================================================================
**measurement**:   ``traffic``
**type**:          ``int``
**fields**:        ``rx_bytes``, ``tx_bytes``
**tags**:          .. code-block:: python

                       {
                           "organization_id": "<organization-id-of-the-related-device>",
                           "ifname": "<interface-name>",
                           # optional
                           "location_id": "<location-id-of-the-related-device-if-present>",
                           "floorplan_id": "<floorplan-id-of-the-related-device-if-present>",
                       }
**configuration**: ``traffic``
**charts**:        ``traffic``
================== ==========================================================================

.. figure:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.1/traffic.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.1/traffic.png
    :align: center

.. _wifi_clients:

WiFi Clients
------------

================== ==========================================================================
**measurement**:   ``wifi_clients``
**type**:          ``int``
**fields**:        ``clients``
**tags**:          .. code-block:: python

                       {
                           "organization_id": "<organization-id-of-the-related-device>",
                           "ifname": "<interface-name>",
                           # optional
                           "location_id": "<location-id-of-the-related-device-if-present>",
                           "floorplan_id": "<floorplan-id-of-the-related-device-if-present>",
                       }
**configuration**: ``clients``
**charts**:        ``wifi_clients``
================== ==========================================================================

.. figure:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/wifi-clients.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/wifi-clients.png
    :align: center

.. _memory_usage:

Memory Usage
------------

================== ====================================================
**measurement**:   ``<memory>``
**type**:          ``float``
**fields**:        ``percent_used``, ``free_memory``, ``total_memory``,
                   ``buffered_memory``, ``shared_memory``,
                   ``cached_memory``, ``available_memory``
**configuration**: ``memory``
**charts**:        ``memory``
================== ====================================================

.. figure:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/memory.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/memory.png
    :align: center

.. _cpu_load:

CPU Load
--------

================== ==================================================
**measurement**:   ``load``
**type**:          ``float``
**fields**:        ``cpu_usage``, ``load_1``, ``load_5``, ``load_15``
**configuration**: ``load``
**charts**:        ``load``
================== ==================================================

.. figure:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/cpu-load.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/cpu-load.png
    :align: center

.. _disk_usage:

Disk Usage
----------

================== =============
**measurement**:   ``disk``
**type**:          ``float``
**fields**:        ``used_disk``
**configuration**: ``disk``
**charts**:        ``disk``
================== =============

.. figure:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/disk-usage.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/disk-usage.png
    :align: center

.. _mobile_signal_strength:

Mobile Signal Strength
----------------------

================== =====================================
**measurement**:   ``signal_strength``
**type**:          ``float``
**fields**:        ``signal_strength``, ``signal_power``
**configuration**: ``signal_strength``
**charts**:        ``signal_strength``
================== =====================================

.. figure:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/signal-strength.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/signal-strength.png
    :align: center

.. _mobile_signal_quality:

Mobile Signal Quality
---------------------

================== ======================================
**measurement**:   ``signal_quality``
**type**:          ``float``
**fields**:        ``signal_quality``, ``signal_quality``
**configuration**: ``signal_quality``
**charts**:        ``signal_quality``
================== ======================================

.. figure:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/signal-quality.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/signal-quality.png
    :align: center

.. _mobile_access_technology_in_use:

Mobile Access Technology in Use
-------------------------------

================== ===============
**measurement**:   ``access_tech``
**type**:          ``int``
**fields**:        ``access_tech``
**configuration**: ``access_tech``
**charts**:        ``access_tech``
================== ===============

.. figure:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/access-technology.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/access-technology.png
    :align: center

.. _iperf3:

Iperf3
------

================== =====================================================
**measurement**:   ``iperf3``
**types**:         |   ``int`` (iperf3_result, sent_bytes_tcp,
                       received_bytes_tcp, retransmits, sent_bytes_udp,
                       total_packets, lost_packets),
                   |   ``float`` (sent_bps_tcp, received_bps_tcp,
                       sent_bps_udp, jitter, lost_percent)
**fields**:        |   ``iperf3_result``, ``sent_bps_tcp``,
                       ``received_bps_tcp``, ``sent_bytes_tcp``,
                       ``received_bytes_tcp``, ``retransmits``,
                   |   ``sent_bps_udp``, ``sent_bytes_udp``, ``jitter``,
                       ``total_packets``, ``lost_packets``,
                       ``lost_percent``
**configuration**: ``iperf3``
**charts**:        ``bandwidth``, ``transfer``, ``retransmits``,
                   ``jitter``, ``datagram``, ``datagram_loss``
================== =====================================================

**Bandwidth**:

.. figure:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.1/bandwidth.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.1/bandwidth.png
    :align: center

**Transferred Data**:

.. figure:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.1/transferred-data.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.1/transferred-data.png
    :align: center

**Retransmits**:

.. figure:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.1/retransmits.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.1/retransmits.png
    :align: center

**Jitter**:

.. figure:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.1/jitter.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.1/jitter.png
    :align: center

**Datagram**:

.. figure:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.1/datagram.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.1/datagram.png
    :align: center

**Datagram loss**:

.. figure:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.1/datagram-loss.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.1/datagram-loss.png
    :align: center

For more info on how to configure and use Iperf3, please refer to
:doc:`configuring-iperf3-check`.

.. note::

    Iperf3 charts uses ``connect_points=True`` in :ref:`default chart
    configuration <openwisp_monitoring_charts>` that joins it's individual
    chart data points.

Passive vs Active Metric Collection
-----------------------------------

The the different :doc:`device metric <./metrics>` collected by OpenWISP
Monitoring can be divided in two categories:

1. **metrics collected actively by OpenWISP**: these metrics are collected
   by the celery workers running on the OpenWISP server, which
   continuously sends network requests to the devices and store the
   results;
2. **metrics collected passively by OpenWISP**: these metrics are sent by
   the `openwrt-openwisp-monitoring agent
   <#install-monitoring-packages-on-the-device>`_ installed on the network
   devices and are collected by OpenWISP via its REST API.

The :doc:`checks` section of the documentation lists the currently
implemented **active checks**.
