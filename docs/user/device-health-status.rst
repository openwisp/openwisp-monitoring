Device Health Status
====================

The possible values for the health status field
(``DeviceMonitoring.status``) are explained below.

``UNKNOWN``
-----------

Whenever a new device is created it will have ``UNKNOWN`` as it's default
Heath Status.

It implies that the system doesn't know whether the device is reachable
yet.

``OK``
------

Everything is working normally.

``PROBLEM``
-----------

One of the metrics has a value which is not in the expected range (the
threshold value set in the alert settings has been crossed).

Example: CPU usage should be less than 90% but current value is at 95%.
Or, the device is not reachable by ping check (ping is a critical metric),
but the device is sending passive metrics.

``CRITICAL``
------------

All of the metrics defined in
:ref:`openwisp_monitoring_critical_device_metrics` has a value which is
not in the expected range (the threshold value set in the alert settings
has been crossed).

Example: Both :ref:`ping_check` and :ref:`monitoring_data_collected_check`
is failing for the device.

``DEACTIVATED``
---------------

The device is deactivated. All active and passive checks are disabled.
