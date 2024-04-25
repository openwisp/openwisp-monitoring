Device Health Status
--------------------

The possible values for the health status field (``DeviceMonitoring.status``)
are explained below.

``UNKNOWN``
~~~~~~~~~~~

Whenever a new device is created it will have ``UNKNOWN`` as it's default Heath Status.

It implies that the system doesn't know whether the device is reachable yet.

``OK``
~~~~~~

Everything is working normally.

``PROBLEM``
~~~~~~~~~~~

One of the metrics has a value which is not in the expected range
(the threshold value set in the alert settings has been crossed).

Example: CPU usage should be less than 90% but current value is at 95%.

``CRITICAL``
~~~~~~~~~~~~

One of the metrics defined in ``OPENWISP_MONITORING_CRITICAL_DEVICE_METRICS``
has a value which is not in the expected range
(the threshold value set in the alert settings has been crossed).

Example: ping is by default a critical metric which is expected to be always 1
(reachable).
