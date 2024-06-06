Quickstart Guide
================

Install Monitoring Packages on the Device
-----------------------------------------

`Install the openwrt-openwisp-monitoring packages
<https://github.com/openwisp/openwrt-openwisp-monitoring/tree/0.1.0#install-pre-compiled-packages>`_
on your device.

These packages collect and send the monitoring data from the device to
OpenWISP Monitoring and are required to collect :doc:`metrics <./metrics>`
like interface traffic, WiFi clients, CPU load, memory usage, etc.

.. _openwisp_reach_devices:

Make Sure OpenWISP can Reach your Devices
-----------------------------------------

In order to perform :doc:`active checks <./checks>` and other actions like
:doc:`triggering the push of configuration changes
</controller/user/push-operations>`, :doc:`executing shell commands
</controller/user/shell-commands>`, or :doc:`performing firmware upgrades
</user/firmware-upgrades>`, **the OpenWISP server needs to be able to
reach the network devices**.

There are mainly two deployment scenarios for OpenWISP:

1. the OpenWISP server is deployed on the public internet and the devices
   are geographically distributed across different locations: **in this
   case a management tunnel is needed**
2. the OpenWISP server is deployed on a computer/server which is located
   in the same Layer 2 network (that is, in the same LAN) where the
   devices are located. **in this case a management tunnel is NOT needed**

1. Public Internet Deployment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This is the most common scenario:

- the OpenWISP server is deployed to the public internet, hence the server
  has a public IPv4 (and IPv6) address and usually a valid SSL certificate
  provided by Let's Encrypt or another SSL provider
- the network devices are geographically distributed across different
  locations (different cities, different regions, different countries)

In this scenario, the OpenWISP application will not be able to reach the
devices **unless a management tunnel** is used, for that reason having a
management VPN like OpenVPN, Wireguard, ZeroTier or any other tunneling
solution is paramount, not only to allow OpenWISP to work properly, but
also to be able to perform debugging and troubleshooting when needed.

In this scenario, the following requirements are needed:

- a VPN server must be installed in a way that the OpenWISP server can
  reach the VPN peers, for more information on how to do this via OpenWISP
  please refer to the following sections:

  - :doc:`OpenVPN tunnel automation </user/vpn>`
  - :doc:`Wireguard tunnel automation </controller/user/wireguard>`

  If you prefer to use other tunneling solutions (L2TP, Softether, etc.)
  and know how to configure those solutions on your own, that's totally
  fine as well.

  If the OpenWISP server is connected to a network infrastructure which
  allows it to reach the devices via pre-existing tunneling or Intranet
  solutions (eg: MPLS, SD-WAN), then setting up a VPN server is not
  needed, as long as there's a dedicated interface on OpenWrt which gets
  an IP address assigned to it and which is reachable from the OpenWISP
  server.

- The devices must be configured to join the management tunnel
  automatically, either via a pre-existing configuration in the firmware
  or via an :doc:`OpenWISP Template </controller/user/templates>`.
- The `openwisp-config <https://github.com/openwisp/openwisp-config>`_
  agent on the devices must be configured to specify the
  ``management_interface`` option, the agent will communicate the IP of
  the management interface to the OpenWISP Server and OpenWISP will use
  the management IP for reaching the device.

  For example, if the *management interface* is named ``tun0``, the
  openwisp-config configuration should look like the following example:

.. code-block:: text

    # In /etc/config/openwisp on the device

    config controller 'http'
        # ... other configuration directives ...
        option management_interface 'tun0'

2. LAN Deployment
~~~~~~~~~~~~~~~~~

When the OpenWISP server and the network devices are deployed in the same
L2 network (eg: an office LAN) and the OpenWISP server is reachable on the
LAN address, OpenWISP can then use the **Last IP** field of the devices to
reach them.

In this scenario it's necessary to set the
:ref:`"OPENWISP_MONITORING_MANAGEMENT_IP_ONLY"
<openwisp_monitoring_management_ip_only>` setting to ``False``.
