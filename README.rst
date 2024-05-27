openwisp-monitoring
===================

.. image:: https://github.com/openwisp/openwisp-monitoring/workflows/OpenWISP%20Monitoring%20CI%20Build/badge.svg?branch=master
    :target: https://github.com/openwisp/openwisp-monitoring/actions?query=workflow%3A%22OpenWISP+Monitoring+CI+Build%22
    :alt: CI build status

.. image:: https://coveralls.io/repos/github/openwisp/openwisp-monitoring/badge.svg?branch=master
    :target: https://coveralls.io/github/openwisp/openwisp-monitoring?branch=master
    :alt: Test coverage

.. image:: https://img.shields.io/librariesio/github/openwisp/openwisp-monitoring
    :target: https://libraries.io/github/openwisp/openwisp-monitoring#repository_dependencies
    :alt: Dependency monitoring

.. image:: https://badge.fury.io/py/openwisp-monitoring.svg
    :target: http://badge.fury.io/py/openwisp-monitoring
    :alt: pypi

.. image:: https://pepy.tech/badge/openwisp-monitoring
    :target: https://pepy.tech/project/openwisp-monitoring
    :alt: downloads

.. image:: https://img.shields.io/gitter/room/nwjs/nw.js.svg?style=flat-square
    :target: https://gitter.im/openwisp/monitoring
    :alt: support chat

.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
    :target: https://pypi.org/project/black/
    :alt: code style: black

.. image:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/monitoring-demo.gif
    :target: https://github.com/openwisp/openwisp-monitoring/tree/docs/docs/monitoring-demo.gif
    :alt: Feature Highlights

----

**Need a quick overview?** `Try the OpenWISP Demo
<https://openwisp.org/demo.html>`_.

OpenWISP Monitoring is a network monitoring system written in Python and
Django, designed to be **extensible**, **programmable**, **scalable** and
easy to use by end users: once the system is configured, monitoring
checks, alerts and metric collection happens automatically.

See the `available features <#available-features>`_.

`OpenWISP <http://openwisp.org>`_ is not only an application designed for
end users, but can also be used as a framework on which custom network
automation solutions can be built on top of its building blocks.

Other popular building blocks that are part of the OpenWISP ecosystem are:

- `openwisp-controller
  <https://github.com/openwisp/openwisp-controller>`_: network and WiFi
  controller: provisioning, configuration management, x509 PKI management
  and more; works on OpenWRT, but designed to work also on other systems.
- `openwisp-network-topology
  <https://github.com/openwisp/openwisp-network-topology>`_: provides way
  to collect and visualize network topology data from dynamic mesh routing
  daemons or other network software (eg: OpenVPN); it can be used in
  conjunction with openwisp-monitoring to get a better idea of the state
  of the network
- `openwisp-firmware-upgrader
  <https://github.com/openwisp/openwisp-firmware-upgrader>`_: automated
  firmware upgrades (single device or mass network upgrades)
- `openwisp-radius <https://github.com/openwisp/openwisp-radius>`_: based
  on FreeRADIUS, allows to implement network access authentication systems
  like 802.1x WPA2 Enterprise, captive portal authentication, Hotspot 2.0
  (802.11u)
- `openwisp-ipam <https://github.com/openwisp/openwisp-ipam>`_: it allows
  to manage the IP address space of networks

**For a more complete overview of the OpenWISP modules and architecture**,
see the `OpenWISP Architecture Overview
<https://openwisp.io/docs/general/architecture.html>`_.

.. figure:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/dashboard.png
    :align: center

Available Features
------------------

- Collection of monitoring information in a timeseries database (currently
  only influxdb is supported)
- Allows to browse alerts easily from the user interface with one click
- Collects and displays `device status <#device-status>`_ information like
  uptime, RAM status, CPU load averages, Interface properties and
  addresses, WiFi interface status and associated clients, Neighbors
  information, DHCP Leases, Disk/Flash status
- Monitoring charts for `uptime <#ping>`_, `packet loss <#ping>`_, `round
  trip time (latency) <#ping>`_, `associated wifi clients
  <#wifi-clients>`_, `interface traffic <#traffic>`_, `RAM usage
  <#memory-usage>`_, `CPU load <#cpu-load>`_, `flash/disk usage
  <#disk-usage>`_, mobile signal (LTE/UMTS/GSM `signal strength
  <#mobile-signal-strength>`_, `signal quality <#mobile-signal-quality>`_,
  `access technology in use <#mobile-access-technology-in-use>`_),
  `bandwidth <#iperf3>`_, `transferred data <#iperf3>`_, `restransmits
  <#iperf3>`_, `jitter <#iperf3>`_, `datagram <#iperf3>`_, `datagram loss
  <#iperf3>`_
- Maintains a record of `WiFi sessions <#monitoring-wifi-sessions>`_ with
  clients' MAC address and vendor, session start and stop time and
  connected device along with other information
- Charts can be viewed at resolutions of the last 1 day, 3 days, 7 days,
  30 days, and 365 days
- Configurable alerts
- CSV Export of monitoring data
- An overview of the status of the network is shown in the admin
  dashboard, a chart shows the percentages of devices which are online,
  offline or having issues; there are also `two timeseries charts which
  show the total unique WiFI clients and the traffic flowing to the
  network <dashboard-monitoring-charts>`_, a geographic map is also
  available for those who use the geographic features of OpenWISP
- Possibility to configure additional `Metrics
  <#openwisp_monitoring_metrics>`_ and `Charts
  <#openwisp_monitoring_charts>`_
- Extensible active check system: it's possible to write additional checks
  that are run periodically using python classes
- Extensible metrics and charts: it's possible to define new metrics and
  new charts
- API to retrieve the chart metrics and status information of each device
  based on `NetJSON DeviceMonitoring
  <http://netjson.org/docs/what.html#devicemonitoring>`_
- `Iperf3 check <#iperf3-1>`_ that provides network performance
  measurements such as maximum achievable bandwidth, jitter, datagram loss
  etc of the openwrt device using `iperf3 utility <https://iperf.fr/>`_

----

.. contents:: **Table of Contents**:
    :backlinks: none
    :depth: 3

----

Contributing
------------

Please refer to the `OpenWISP contributing guidelines
<http://openwisp.io/docs/developer/contributing.html>`_.
