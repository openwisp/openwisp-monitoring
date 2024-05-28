Checks
======

.. _ping_check:

Ping
----

This check returns information on device ``uptime`` and ``RTT (Round trip
time)``. The Charts ``uptime``, ``packet loss`` and ``rtt`` are created.
The ``fping`` command is used to collect these metrics. You may choose to
disable auto creation of this check by setting
:ref:`openwisp_monitoring_auto_ping` to ``False``.

You can change the default values used for ping checks using
:ref:`openwisp_monitoring_ping_check_config` setting.

.. _config_applied_check:

Configuration applied
---------------------

This check ensures that the `openwisp-config agent
<https://github.com/openwisp/openwisp-config/>`_ is running and applying
configuration changes in a timely manner. You may choose to disable auto
creation of this check by using the setting
:ref:`openwisp_monitoring_auto_device_config_check`.

This check runs periodically, but it is also triggered whenever the
configuration status of a device changes, this ensures the check reacts
quickly to events happening in the network and informs the user promptly
if there's anything that is not working as intended.

.. _iperf3_check:

Iperf3
------

This check provides network performance measurements such as maximum
achievable bandwidth, jitter, datagram loss etc of the device using
`iperf3 utility <https://iperf.fr/>`_.

This check is **disabled by default**. You can enable auto creation of
this check by setting the :ref:`openwisp_monitoring_auto_iperf3` to
``True``.

You can also :ref:`add the iperf3 check <adding_checks_and_alertsettings>`
directly from the device page.

It also supports tuning of various parameters. You can change the
parameters used for iperf3 checks (e.g. timing, port, username, password,
rsa_publc_key etc) using the
:ref:`openwisp_monitoring_iperf3_check_config` setting.

.. note::

    When setting :ref:`openwisp_monitoring_auto_iperf3` to ``True``, you
    may need to update the :ref:`metric configuration <Adding Checks and
    Alert settings from the device page>` to enable alerts for the iperf3
    check.

Alerts / Notifications
----------------------

The following kind of notifications will be sent based on the check
results:

- ``threshold_crossed``: Fires when a metric crosses the boundary defined
  in the threshold value of the alert settings.
- ``threhold_recovery``: Fires when a metric goes back within the expected
  range.
- ``connection_is_working``: Fires when the connection to a device is
  working.
- ``connection_is_not_working``: Fires when the connection (eg: SSH) to a
  device stops working (eg: credentials are outdated, management IP
  address is outdated, or device is not reachable).
