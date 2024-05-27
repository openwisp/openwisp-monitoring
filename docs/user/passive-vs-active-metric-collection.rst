Passive vs Active Metric Collection
===================================

The `the different device metric
<https://github.com/openwisp/openwisp-monitoring#default-metrics>`_
collected by OpenWISP Monitoring can be divided in two categories:

1. **metrics collected actively by OpenWISP**: these metrics are collected
   by the celery workers running on the OpenWISP server, which
   continuously sends network requests to the devices and store the
   results;
2. **metrics collected passively by OpenWISP**: these metrics are sent by
   the `openwrt-openwisp-monitoring agent
   <#install-monitoring-packages-on-the-device>`_ installed on the network
   devices and are collected by OpenWISP via its REST API.

The `"Available Checks" <#available-checks>`_ section of this document
lists the currently implemented **active checks**.
