Checks
======

.. contents:: **Table of contents**:
    :depth: 2
    :local:

.. _ping_check:

Ping
----

This check returns information on Ping Success Rate and RTT (Round trip time).
It creates charts like Ping Success Rate, Packet Loss and RTT.
These metrics are collected using the ``fping`` Linux program.
You may choose to disable auto creation of this check by setting
:ref:`openwisp_monitoring_auto_ping` to ``False``.

You can change the default values used for ping checks using
:ref:`openwisp_monitoring_ping_check_config` setting.

.. _config_applied_check:

Configuration Applied
---------------------

This check ensures that the :doc:`openwisp-config agent
</openwrt-config-agent/index>` is running and applying configuration
changes in a timely manner. You may choose to disable auto creation of
this check by using the setting
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

You can also :doc:`add the iperf3 check <adding-checks-and-alertsettings>`
directly from the device page.

It also supports tuning of various parameters. You can change the
parameters used for iperf3 checks (e.g. timing, port, username, password,
rsa_publc_key etc) using the
:ref:`openwisp_monitoring_iperf3_check_config` setting.

.. note::

    When setting :ref:`openwisp_monitoring_auto_iperf3` to ``True``, you
    may need to update the :doc:`metric configuration
    <adding-checks-and-alertsettings>` to enable alerts for the iperf3
    check.
