Device Checks & Alert Settings
==============================

We can add checks and define alert settings directly from the **device
page**.

To add a check, you just need to select an available **check type** as
shown below:

.. figure:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.1/device-inline-check.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.1/device-inline-check.png
    :align: center

The following example shows how to use the
:ref:`openwisp_monitoring_metrics` setting to reconfigure the system for
:ref:`iperf3 check <iperf3_check>` to send an alert if the measured **TCP
bandwidth** has been less than **10Mbit/s** for more than **2 days**.

1. By default, :ref:`Iperf3 checks <iperf3_check>` come with default alert
settings, but it is easy to customize alert settings through the device
page as shown below:

.. figure:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.1/device-inline-alertsettings.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.1/device-inline-alertsettings.png
    :align: center

2. Now, add the following notification configuration to send an alert for
   **TCP bandwidth**:

.. code-block:: python

    # Main project settings.py
    from django.utils.translation import gettext_lazy as _

    OPENWISP_MONITORING_METRICS = {
        "iperf3": {
            "notification": {
                "problem": {
                    "verbose_name": "Iperf3 PROBLEM",
                    "verb": _("Iperf3 bandwidth is less than normal value"),
                    "level": "warning",
                    "email_subject": _(
                        "[{site.name}] PROBLEM: {notification.target} {notification.verb}"
                    ),
                    "message": _(
                        "The device [{notification.target}]({notification.target_link}) "
                        "{notification.verb}."
                    ),
                },
                "recovery": {
                    "verbose_name": "Iperf3 RECOVERY",
                    "verb": _("Iperf3 bandwidth now back to normal"),
                    "level": "info",
                    "email_subject": _(
                        "[{site.name}] RECOVERY: {notification.target} {notification.verb}"
                    ),
                    "message": _(
                        "The device [{notification.target}]({notification.target_link}) "
                        "{notification.verb}."
                    ),
                },
            },
        },
    }

.. figure:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.1/alert_field_warn.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.1/alert_field_warn.png
    :align: center

.. figure:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.1/alert_field_info.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.1/alert_field_info.png
    :align: center

.. note::

    To access the features described above, the user must have permissions
    for ``Check`` and ``AlertSetting`` *inlines*, these permissions are
    included by default in the "Administrator" and "Operator" groups and
    are shown in the screenshot below.

.. figure:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.1/inline-permissions.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.1/inline-permissions.png
    :align: center

How is Historical Data Handled?
-------------------------------

The :doc:`OpenWrt Monitoring Agent </openwrt-monitoring-agent/index>`
collects and :ref:`temporarily stores monitoring data locally on the
device <monitoring_agent_send_mode>` when it cannot reach OpenWISP, for
example, during network or server outages.

OpenWISP Monitoring supports the submission of historical data, meaning
monitoring information that could not be delivered in real time and is
sent at a later stage. This capability makes both the agent and the server
resilient to occasional disruptions.

However, it's important to note that **historical data does not trigger
alerts** or affect the **health status** of a device. Threshold checks and
health evaluations are only applied to fresh data. This approach prevents
conflicts between outdated information and the device's current state,
which may have changed significantly.
