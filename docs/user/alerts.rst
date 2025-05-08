Alerts
======

.. contents:: **Table of contents**:
    :depth: 2
    :local:

An alert is triggered when a device metric (e.g., ping, CPU usage) crosses
its configured threshold for a specified duration (tolerance). A recovery
alert is sent when the metric returns to normal.

Alerts are based on **Alert Settings** defined for each metric, each
setting includes:

- **Operator**: defines the condition to evaluate the metric value:

  - **Greater than**: triggers when the value exceeds the threshold.
  - **Less than**: triggers when the value is below the threshold.

- **Threshold**: the metric value that triggers the alert.
- **Tolerance**: the duration (in minutes) for which the threshold must be
  breached before an alert is triggered.

OpenWISP Monitoring provides built-in alerts for the following metrics:

.. note::

    You can override the default alert settings globally using the
    :ref:`openwisp_monitoring_metrics` setting, or on a per-device basis
    as explained in the :doc:`device-checks-and-alert-settings` section.

.. _ping_alert:

Ping
----

Triggers when the device becomes unreachable via ping. This alert is
enabled by default.

**Default Alert Settings:**

========= =================
Operator  ``< (less than)``
Threshold ``1``
Tolerance ``0`` minutes
========= =================

.. note::

    The :ref:`ping_check` check should be enabled for the device to
    receive this alert.

.. _configuration_applied_alert:

Config Applied
--------------

Triggers when the device fails to apply configuration changes within the
specified time. This alert is enabled by default.

**Default Alert Settings:**

========= =================
Operator  ``< (less than)``
Threshold ``1``
Tolerance ``5`` minutes
========= =================

.. note::

    The :ref:`config_applied_check` check should be enabled for the device
    to receive this alert.

.. _monitoring_data_collected_alert:

Data Collected
--------------

Triggers when no metric data has been collected from the device. This
alert is enabled by default.

**Default Alert Settings:**

========= =================
Operator  ``< (less than)``
Threshold ``1``
Tolerance ``30`` minutes
========= =================

.. note::

    The :ref:`monitoring_data_collected_check` check should be enabled for
    the device to receive this alert.

CPU Usage
---------

Triggers when CPU usage exceeds the threshold. This alert is enabled by
default.

**Default Alert Settings:**

========= ====================
Operator  ``> (greater than)``
Threshold ``90`` (percent)
Tolerance ``5`` minutes
========= ====================

Memory Usage
------------

Triggers when memory usage exceeds the threshold. This alert is enabled by
default.

**Default Alert Settings:**

========= ====================
Operator  ``> (greater than)``
Threshold ``95`` (percent)
Tolerance ``5`` minutes
========= ====================

Disk Usage
----------

Triggers when disk usage exceeds the threshold. This alert is enabled by
default.

**Default Alert Settings:**

========= ====================
Operator  ``> (greater than)``
Threshold ``90`` (percent)
Tolerance ``0`` minutes
========= ====================

.. _wifi_clients_alert:

WiFi Clients (Max)
------------------

Triggers when the number of connected WiFi clients exceeds the threshold.
This alert is disabled by default.

**Default Alert Settings:**

========= ====================
Operator  ``> (greater than)``
Threshold ``50``
Tolerance ``120`` minutes
========= ====================

.. note::

    The :ref:`wifi_clients_check` check should be enabled for the device
    to receive this alert.

WiFi Clients (Min)
------------------

Triggers when the number of connected WiFi clients falls below the
threshold. This alert is disabled by default.

**Default Alert Settings:**

========= =================
Operator  ``< (less than)``
Threshold ``1``
Tolerance ``0`` minutes
========= =================

.. note::

    The :ref:`wifi_clients_check` check should be enabled for the device
    to receive this alert.
