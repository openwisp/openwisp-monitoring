Managing Device Checks & Alert Settings
=======================================

**Overview of default checks**

1. Ping Check
------------
* **Triggers when**: Value is less than 1
* **Wait time**: 0 minutes (immediate)
* **Sets status**: Critical
* **Meaning**: Device is unreachable

2. Config Applied Check
---------------------
* **Triggers when**: Value is less than 1
* **Wait time**: 5 minutes
* **Sets status**: Problem
* **Meaning**: Configuration hasn't been updated for over 5 minutes

3. WiFi Clients Check
-------------------
Maximum:
^^^^^^^^
* **Triggers when**: More than 50 clients
* **Wait time**: 120 minutes (2 hours)
* **Sets status**: Problem
* **Meaning**: Too many clients connected

Minimum:
^^^^^^^^
* **Triggers when**: Less than 1 client
* **Wait time**: 0 minutes (immediate)
* **Sets status**: Problem
* **Meaning**: No clients connected

4. Disk Usage Check
-----------------
* **Triggers when**: Usage exceeds 90%
* **Wait time**: 0 minutes (immediate)
* **Sets status**: Problem
* **Meaning**: Disk space is nearly full

5. Memory Usage Check
-------------------
* **Triggers when**: Usage exceeds 95%
* **Wait time**: 5 minutes
* **Sets status**: Problem
* **Meaning**: High memory consumption persists

6. CPU Usage Check
----------------
* **Triggers when**: Usage exceeds 90%
* **Wait time**: 5 minutes
* **Sets status**: Problem
* **Meaning**: High CPU load persists

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
