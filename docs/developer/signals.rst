Signals
-------

``device_metrics_received``
~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Path**: ``openwisp_monitoring.device.signals.device_metrics_received``

**Arguments**:

- ``instance``: instance of ``Device`` whose metrics have been received
- ``request``: the HTTP request object
- ``time``: time with which metrics will be saved. If none, then server time will be used
- ``current``: whether the data has just been collected or was collected previously and sent now due to network connectivity issues

This signal is emitted when device metrics are received to the ``DeviceMetric``
view (only when using HTTP POST).

The signal is emitted just before a successful response is returned,
it is not sent if the response was not successful.

``health_status_changed``
~~~~~~~~~~~~~~~~~~~~~~~~~

**Path**: ``openwisp_monitoring.device.signals.health_status_changed``

**Arguments**:

- ``instance``: instance of ``DeviceMonitoring`` whose status has been changed
- ``status``: the status by which DeviceMonitoring's existing status has been updated with

This signal is emitted only if the health status of DeviceMonitoring object gets updated.

``threshold_crossed``
~~~~~~~~~~~~~~~~~~~~~

**Path**: ``openwisp_monitoring.monitoring.signals.threshold_crossed``

**Arguments**:

- ``metric``: ``Metric`` object whose threshold defined in related alert settings was crossed
- ``alert_settings``: ``AlertSettings`` related to the ``Metric``
- ``target``: related ``Device`` object
- ``first_time``: it will be set to true when the metric is written for the first time. It shall be set to false afterwards.
- ``tolerance_crossed``: it will be set to true if the metric has crossed the threshold for tolerance configured in alert settings.
  Otherwise, it will be set to false.

``first_time`` parameter can be used to avoid initiating unneeded actions.
For example, sending recovery notifications.

This signal is emitted when the threshold value of a ``Metric`` defined in
alert settings is crossed.

``pre_metric_write``
~~~~~~~~~~~~~~~~~~~~

**Path**: ``openwisp_monitoring.monitoring.signals.pre_metric_write``

**Arguments**:

- ``metric``: ``Metric`` object whose data shall be stored in timeseries database
- ``values``: metric data that shall be stored in the timeseries database
- ``time``: time with which metrics will be saved
- ``current``: whether the data has just been collected or was collected previously and sent now due to network connectivity issues

This signal is emitted for every metric before the write operation is sent to
the timeseries database.

``post_metric_write``
~~~~~~~~~~~~~~~~~~~~~

**Path**: ``openwisp_monitoring.monitoring.signals.post_metric_write``

**Arguments**:

- ``metric``: ``Metric`` object whose data is being stored in timeseries database
- ``values``: metric data that is being stored in the timeseries database
- ``time``: time with which metrics will be saved
- ``current``: whether the data has just been collected or was collected previously and sent now due to network connectivity issues

This signal is emitted for every metric after the write operation is successfully
executed in the background.
