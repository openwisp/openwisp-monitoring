Exceptions
==========

.. include:: /partials/developers-docs-warning.rst

``TimeseriesWriteException``
----------------------------

**Path**: ``openwisp_monitoring.db.exceptions.TimeseriesWriteException``

If there is any failure due while writing data in timeseries database,
this exception shall be raised with a helpful error message explaining the
cause of the failure. This exception will normally be caught and the
failed write task will be retried in the background so that there is no
loss of data if failures occur due to overload of Timeseries server. You
can read more about this retry mechanism at
`OPENWISP_MONITORING_WRITE_RETRY_OPTIONS
<#openwisp-monitoring-write-retry-options>`_.

``InvalidMetricConfigException``
--------------------------------

**Path**:
``openwisp_monitoring.monitoring.exceptions.InvalidMetricConfigException``

This exception shall be raised if the metric configuration is broken.

``InvalidChartConfigException``
-------------------------------

**Path**:
``openwisp_monitoring.monitoring.exceptions.InvalidChartConfigException``

This exception shall be raised if the chart configuration is broken.
