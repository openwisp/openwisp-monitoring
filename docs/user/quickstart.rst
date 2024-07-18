Quick Start Guide
=================

.. contents:: **Table of contents**:
    :depth: 2
    :local:

.. _install_monitoring_packages_on_device:

Install Monitoring Packages on the Device
-----------------------------------------

First of all, :doc:`Install the OpenWrt Monitoring Agent
</openwrt-monitoring-agent/user/quickstart>` on your device.

The agent is responsible for collecting some of the :doc:`monitoring
metrics <./metrics>` from the device and sending these to the server. It's
required to collect interface traffic, WiFi clients, CPU load, memory
usage, storage usage, cellular signal strength, etc.

.. _openwisp_reach_devices:

Make Sure OpenWISP can Reach your Devices
-----------------------------------------

Please make sure that :doc:`OpenWISP can reach your devices </user/vpn>`.
