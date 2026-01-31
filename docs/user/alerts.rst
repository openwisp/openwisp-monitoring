Alerts
======

.. contents:: **Table of contents**:
    :depth: 2
    :local:

Introduction
------------

An alert is triggered when a device metric (e.g., ping, CPU usage) crosses
its configured threshold for a specified duration (tolerance). A recovery
alert is sent when the metric returns to normal.

Alerts are based on **Alert Settings** defined for each metric, each
setting includes:

- **Operator**: defines the condition to evaluate the metric value:

  - **Greater than**: triggers when the value exceeds the threshold.
  - **Less than**: triggers when the value is below the threshold.

- **Threshold**: the metric value that triggers the alert.
- **Tolerance**: the duration (in minutes) the threshold must be
  continuously breached before triggering an alert. Helps reduce noise
  from flapping metrics.

.. note::

    You can override the default alert settings globally using the
    :ref:`openwisp_monitoring_metrics` setting, or on a per-device basis
    as explained in the :doc:`device-checks-and-alert-settings` section.

The built-in alerts are explained below.

.. _ping_alert:

Ping
----

Triggers when the device becomes unreachable via ping.

**Alert enabled by default?** Yes.

**Collected via**: :ref:`Ping Check <ping_check>`.

**Charts**: :ref:`Ping Chart <ping>`.

**Default Alert Settings:**

========= =================
Operator  ``< (less than)``
Threshold ``1``
Tolerance ``30`` minutes
========= =================

.. _configuration_applied_alert:

Config Applied
--------------

Triggers when the device fails to apply configuration changes within the
specified time.

**Alert enabled by default?** Yes.

**Collected via**: :ref:`Config Applied Check <config_applied_check>`.

**Default Alert Settings:**

========= =================
Operator  ``< (less than)``
Threshold ``1``
Tolerance ``10`` minutes
========= =================

.. _monitoring_data_collected_alert:

Data Collected
--------------

Triggers when no metric data has been collected from the device.

**Alert enabled by default?** Yes.

**Collected via**: :ref:`Config Applied Check
<monitoring_data_collected_check>`.

**Default Alert Settings:**

========= =================
Operator  ``< (less than)``
Threshold ``1``
Tolerance ``30`` minutes
========= =================

.. _memory_usage_alert:

Memory Usage
------------

Triggers when memory usage exceeds the threshold.

**Alert enabled by default?** Yes.

**Collected via**: :doc:`OpenWrt Monitoring Agent
</openwrt-monitoring-agent/index>`.

**Charts**: :ref:`Memory Usage Chart <memory_usage>`.

**Default Alert Settings:**

========= ====================
Operator  ``> (greater than)``
Threshold ``95`` (percent)
Tolerance ``30`` minutes
========= ====================

.. _cpu_load_alert:

CPU Load Average
----------------

Triggers when CPU usage exceeds the threshold.

**Alert enabled by default?** Yes.

**Collected via**: :doc:`OpenWrt Monitoring Agent
</openwrt-monitoring-agent/index>`.

**Charts**: :ref:`CPU Load Chart <cpu_load_averages>`.

**Default Alert Settings:**

========= ====================
Operator  ``> (greater than)``
Threshold ``90`` (percent)
Tolerance ``30`` minutes
========= ====================

.. _disk_usage_alert:

Disk Usage
----------

Triggers when disk usage exceeds the threshold.

**Alert enabled by default?** Yes.

**Collected via**: :doc:`OpenWrt Monitoring Agent
</openwrt-monitoring-agent/index>`.

**Charts**: :ref:`Disk Usage Chart <disk_usage>`.

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

**Alert enabled by default?** No (see :ref:`WiFi Clients Check
<wifi_clients_check>` for details on how to enable it).

**Collected via**: the WiFi clients information is collected through the
:doc:`OpenWrt Monitoring Agent </openwrt-monitoring-agent/index>`, but the
alert is triggered by the :ref:`WiFi Clients Check <wifi_clients_check>`.

**Default Alert Settings:**

========= ====================
Operator  ``> (greater than)``
Threshold ``50``
Tolerance ``120`` minutes
========= ====================

WiFi Clients (Min)
------------------

Triggers when the number of connected WiFi clients falls below the
threshold.

**Alert enabled by default?** No (see :ref:`WiFi Clients Check
<wifi_clients_check>` for details on how to enable it).

**Collected via**: the WiFi clients information is collected through the
:doc:`OpenWrt Monitoring Agent </openwrt-monitoring-agent/index>`, but the
alert is triggered by the :ref:`WiFi Clients Check <wifi_clients_check>`.

**Default Alert Settings:**

========= =================
Operator  ``< (less than)``
Threshold ``1``
Tolerance ``0`` minutes
========= =================
