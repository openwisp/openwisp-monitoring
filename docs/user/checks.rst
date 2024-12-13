Checks
======

.. contents:: **Table of contents**:
    :depth: 2
    :local:

.. _ping_check:

Ping
----

This check returns information on Ping Success Rate and RTT (Round trip
time). It creates charts like Ping Success Rate, Packet Loss and RTT.
These metrics are collected using the ``fping`` Linux program. You may
choose to disable auto creation of this check by setting
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

.. _wifi_client_check:

WiFi Client
-----------

This check sends alerts based on the total number of WiFi Clients
connected to a device. It sends two types of alerts:

- **Maximum WiFi Users**: When the total number of WiFi clients connected
  to an access point exceeds a predetermined threshold. This functionality
  provides valuable insights into the network's performance, signaling
  when a specific access point is overwhelmed by an excessive number of
  WiFi users.
- **Minimum WiFi Users**: When the total number of WiFi clients connected
  to an access point remains at zero for a duration exceeding the
  specified tolerance period. It serves as an indicator of whether the
  access point is malfunctioning or if its placement is hindering user
  connectivity.

This check is **disabled by default**. To enable auto creation of this
check, set :ref:`openwisp_monitoring_auto_wifi_client_check` to ``True``
and configure the task scheduling in your Django project:

.. code-block:: python

    from datetime import timedelta

    OPENWISP_MONITORING_AUTO_WIFI_CLIENT_CHECK = True
    CELERY_BEAT_SCHEDULE.update(
        {
            "run_wifi_client_checks": {
                "task": "openwisp_monitoring.check.tasks.run_wifi_client_checks",
                # Run check every 5 minutes
                "schedule": timedelta(minutes=5),
                "relative": True,
            },
        }
    )

You can also :doc:`add the WiFi Client check
<device-checks-and-alert-settings>` directly from the device page.

You can use the
:ref:`openwisp_monitoring_wifi_client_check_snooze_schedule` setting to
disable this check on specific dates, such as during scheduled
maintenance, to avoid generating unnecessary alerts.
