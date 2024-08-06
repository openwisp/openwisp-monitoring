Managing Device Checks & Alert Settings
=======================================

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
