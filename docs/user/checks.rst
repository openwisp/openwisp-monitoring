Checks
======

.. contents:: **Table of contents**:
    :depth: 2
    :local:

Introduction
------------

Active checks are periodic background tasks executed by `Celery workers
<https://docs.celeryq.dev/en/stable/>`_ on the OpenWISP server.

These workers perform the enabled checks and store their results in the
time series database.

The built-in checks and the related django settings available in OpenWISP
Monitoring are described below.

.. include:: /partials/settings-note.rst

.. _ping_check:

Ping
----

**Check enabled by default?** Yes.

**Alert**: :ref:`Ping Alert <ping_alert>`.

**Charts**: :ref:`Ping Charts <ping>`.

This check returns information on Ping Success Rate and RTT (Round trip
time). It creates charts like Ping Success Rate, Packet Loss and RTT.
These metrics are collected using the ``fping`` Linux program. You may
choose to disable auto creation of this check by setting
:ref:`openwisp_monitoring_auto_ping` to ``False``.

You can change the default values used for ping checks using
:ref:`openwisp_monitoring_ping_check_config` setting.

This check also :ref:`sends an alert when the device becomes unreachable
<ping_alert>`.

.. _config_applied_check:

Configuration Applied
---------------------

**Check enabled by default?** Yes.

**Alert**: :ref:`Config Applied Alert <configuration_applied_alert>`.

This check ensures that the :doc:`openwisp-config agent
</openwrt-config-agent/index>` is running and applying configuration
changes in a timely manner. You may choose to disable auto creation of
this check by using the setting
:ref:`openwisp_monitoring_auto_device_config_check`.

This check runs periodically, but it is also triggered whenever the
configuration status of a device changes, this ensures the check reacts
quickly to events happening in the network and informs the user promptly
if there's anything that is not working as intended.

This check also :ref:`sends an alert if configuration is not being applied
<configuration_applied_alert>`.

.. _monitoring_data_collected_check:

Monitoring Data Collected
-------------------------

**Check enabled by default?** Yes.

**Alert**: :ref:`Data Collected Alert <monitoring_data_collected_alert>`.

This check ensures that the server is receiving metrics from network
devices in a timely manner. You may choose to disable auto creation of
this check by using the setting
:ref:`openwisp_monitoring_auto_data_collected_check`.

This check also :ref:`sends an alert when no data is received from a
device <monitoring_data_collected_alert>`.

.. _iperf3_check:

Iperf3
------

**Check enabled by default?** No.

**Charts**: :ref:`Iperf3 Charts <iperf3>`.

This check provides network performance measurements such as maximum
achievable bandwidth, jitter, datagram loss etc of the device using
`iperf3 utility <https://iperf.fr/>`_.

This check is **disabled by default**. You can enable auto creation of
this check by setting :ref:`openwisp_monitoring_auto_iperf3` to ``True``.

You can also :doc:`add the iperf3 check
<device-checks-and-alert-settings>` directly from the device page.

It also supports tuning of various parameters. You can change the
parameters used for iperf3 checks (e.g. timing, port, username, password,
``rsa_publc_key``, etc.) using the
:ref:`openwisp_monitoring_iperf3_check_config` setting.

.. note::

    When setting :ref:`openwisp_monitoring_auto_iperf3` to ``True``, you
    may need to update the :doc:`metric configuration
    <device-checks-and-alert-settings>` to enable alerts for the iperf3
    check.

.. _wifi_clients_check:

WiFi Clients
------------

**Check enabled by default?** No.

**Alerts**: :ref:`WiFi Clients Alerts (Max/Min) <wifi_clients_alert>`.

This check sends alerts based on the total number of WiFi Clients
connected to a device. It sends two types of alerts:

- **Maximum WiFi Clients**: When the total number of WiFi clients
  connected to an access point exceeds a predetermined threshold. This
  functionality provides valuable insights into the network's performance,
  signaling when a specific access point is overwhelmed by an excessive
  number of WiFi clients.
- **Minimum WiFi Clients**: When the total number of WiFi clients
  connected to an access point remains at zero for a duration exceeding
  the specified tolerance period. It serves as an indicator of whether the
  access point is malfunctioning or if its placement is hindering user
  connectivity.

This check is **disabled by default**. To enable auto creation of this
check, set :ref:`openwisp_monitoring_auto_wifi_clients_check` to ``True``.

You can also :doc:`add the WiFi Clients check
<device-checks-and-alert-settings>` directly from the device page.

You can use the
:ref:`openwisp_monitoring_wifi_clients_check_snooze_schedule` setting to
disable this check on specific dates, such as during scheduled
maintenance, to avoid generating unnecessary alerts.

Other related settings:

- :ref:`openwisp_monitoring_wifi_clients_max_check_interval`
- :ref:`openwisp_monitoring_wifi_clients_min_check_interval`
