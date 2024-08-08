Monitoring: Features
====================

OpenWISP provides the following monitoring capabilities:

- An overview of the status of the network is shown in the admin
  dashboard, a chart shows the percentages of devices which are online,
  offline or having issues; there are also :doc:`two timeseries charts
  which show the total unique WiFI clients and the traffic flowing to the
  network <dashboard-monitoring-charts>`, a geographic map is also
  available for those who use the geographic features of OpenWISP
- Collection of monitoring information in a timeseries database (currently
  only **InfluxDB** is supported)
- Allows to browse alerts easily from the user interface with one click
- Collects and displays :ref:`device status <device_status>` information
  like uptime, RAM status, CPU load averages, Interface properties and
  addresses, WiFi interface status and associated clients, Neighbors
  information, DHCP Leases, Disk/Flash status
- Monitoring charts for :ref:`ping success rate <ping_check>`,
  :ref:`packet loss <ping_check>`, :ref:`round trip time (latency)
  <ping_check>`, :ref:`associated wifi clients <wifi_clients>`,
  :ref:`interface traffic <traffic>`, :ref:`RAM usage <memory_usage>`,
  :ref:`CPU load <cpu_load>`, :ref:`flash/disk usage <disk_usage>`, mobile
  signal (LTE/UMTS/GSM :ref:`signal strength <mobile_signal_strength>`,
  :ref:`signal quality <mobile_signal_quality>`, :ref:`access technology
  in use <mobile_access_technology_in_use>`), :ref:`bandwidth <iperf3>`,
  :ref:`transferred data <iperf3>`, :ref:`restransmits <iperf3>`,
  :ref:`jitter <iperf3>`, :ref:`datagram <iperf3>`, :ref:`datagram loss
  <iperf3>`
- Maintains a record of :doc:`WiFi sessions <wifi-sessions>` with clients'
  MAC address and vendor, session start and stop time and connected device
  along with other information
- Charts can be viewed at resolutions of the last 1 day, 3 days, 7 days,
  30 days, and 365 days
- Configurable alerts
- CSV Export of monitoring data
- Possibility to configure additional :ref:`Metrics
  <openwisp_monitoring_metrics>` and :ref:`Charts
  <openwisp_monitoring_charts>`
- :doc:`Extensible active check system
  <device-checks-and-alert-settings>`: it's possible to write additional
  checks that are run periodically using python classes
- Extensible :ref:`metrics <openwisp_monitoring_metrics>` and :ref:`charts
  <openwisp_monitoring_charts>`: it's possible to define new metrics and
  new charts
- API to retrieve the chart metrics and status information of each device
  based on `NetJSON DeviceMonitoring
  <http://netjson.org/docs/what.html#devicemonitoring>`_
- :ref:`Iperf3 check <iperf3>` that provides network performance
  measurements such as maximum achievable bandwidth, jitter, datagram loss
  etc of the openwrt device using `iperf3 utility <https://iperf.fr/>`_
