Code Utilities
==============

.. include:: ../partials/developer-docs.rst

.. contents:: **Table of contents**:
    :depth: 1
    :local:

Registering / Unregistering Metric Configuration
------------------------------------------------

**OpenWISP Monitoring** provides registering and unregistering metric
configuration through utility functions
``openwisp_monitoring.monitoring.configuration.register_metric`` and
``openwisp_monitoring.monitoring.configuration.unregister_metric``. Using
these functions you can register or unregister metric configurations from
anywhere in your code.

``register_metric``
~~~~~~~~~~~~~~~~~~~

This function is used to register a new metric configuration from anywhere
in your code.

========================= ================================================
**Parameter**             **Description**
**metric_name**:          A ``str`` defining name of the metric
                          configuration.
**metric_configuration**: A ``dict`` defining configuration of the metric.
========================= ================================================

An example usage has been shown below.

.. code-block:: python

    from django.utils.translation import gettext_lazy as _
    from openwisp_monitoring.monitoring.configuration import register_metric

    # Define configuration of your metric
    metric_config = {
        "label": _("Ping"),
        "name": "Ping",
        "key": "ping",
        "field_name": "reachable",
        "related_fields": ["loss", "rtt_min", "rtt_max", "rtt_avg"],
        "charts": {
            "uptime": {
                "type": "bar",
                "title": _("Ping Success Rate"),
                "description": _(
                    "A value of 100% means reachable, 0% means unreachable, values in "
                    "between 0% and 100% indicate the average reachability in the "
                    "period observed. Obtained with the fping linux program."
                ),
                "summary_labels": [_("Average Ping Success Rate")],
                "unit": "%",
                "order": 200,
                "colorscale": {
                    "max": 100,
                    "min": 0,
                    "label": _("Rate"),
                    "scale": [
                        [
                            [0, "#c13000"],
                            [0.1, "cb7222"],
                            [0.5, "#deed0e"],
                            [0.9, "#7db201"],
                            [1, "#498b26"],
                        ],
                    ],
                    "map": [
                        [100, "#498b26", _("Flawless")],
                        [90, "#7db201", _("Mostly Reachable")],
                        [50, "#deed0e", _("Partly Reachable")],
                        [10, "#cb7222", _("Mostly Unreachable")],
                        [None, "#c13000", _("Unreachable")],
                    ],
                    "fixed_value": 100,
                },
                "query": chart_query["uptime"],
            },
            "packet_loss": {
                "type": "bar",
                "title": _("Packet loss"),
                "description": _(
                    "Indicates the percentage of lost packets observed in ICMP probes. "
                    "Obtained with the fping linux program."
                ),
                "summary_labels": [_("Average packet loss")],
                "unit": "%",
                "colors": "#d62728",
                "order": 210,
                "query": chart_query["packet_loss"],
            },
            "rtt": {
                "type": "scatter",
                "title": _("Round Trip Time"),
                "description": _(
                    "Round trip time observed in ICMP probes, measuered in milliseconds."
                ),
                "summary_labels": [
                    _("Average RTT"),
                    _("Average Max RTT"),
                    _("Average Min RTT"),
                ],
                "unit": _(" ms"),
                "order": 220,
                "query": chart_query["rtt"],
            },
        },
        "alert_settings": {"operator": "<", "threshold": 1, "tolerance": 0},
        "notification": {
            "problem": {
                "verbose_name": "Ping PROBLEM",
                "verb": "cannot be reached anymore",
                "level": "warning",
                "email_subject": _("[{site.name}] {notification.target} is not reachable"),
                "message": _(
                    "The device [{notification.target}] {notification.verb} anymore by our ping "
                    "messages."
                ),
            },
            "recovery": {
                "verbose_name": "Ping RECOVERY",
                "verb": "has become reachable",
                "level": "info",
                "email_subject": _(
                    "[{site.name}] {notification.target} is reachable again"
                ),
                "message": _(
                    "The device [{notification.target}] {notification.verb} again by our ping "
                    "messages."
                ),
            },
        },
    }

    # Register your custom metric configuration
    register_metric("ping", metric_config)

The above example will register one metric configuration (named ``ping``),
three chart configurations (named ``rtt``, ``packet_loss``, ``uptime``) as
defined in the **charts** key, two notification types (named
``ping_recovery``, ``ping_problem``) as defined in **notification** key.

The ``AlertSettings`` of ``ping`` metric will by default use ``threshold``
and ``tolerance`` defined in the ``alert_settings`` key. You can always
override them and define your own custom values via the *admin*.

You can also use the ``alert_field`` key in metric configuration which
allows ``AlertSettings`` to check the ``threshold`` on ``alert_field``
instead of the default ``field_name`` key.

.. note::

    It will raise ``ImproperlyConfigured`` exception if a metric
    configuration is already registered with same name (not to be confused
    with verbose_name).

If you don't need to register a new metric but need to change a specific
key of an existing metric configuration, you can use
:ref:`OPENWISP_MONITORING_METRICS <openwisp_monitoring_metrics>`.

``unregister_metric``
~~~~~~~~~~~~~~~~~~~~~

This function is used to unregister a metric configuration from anywhere
in your code.

================ ====================================================
**Parameter**    **Description**
**metric_name**: A ``str`` defining name of the metric configuration.
================ ====================================================

An example usage is shown below.

.. code-block:: python

    from openwisp_monitoring.monitoring.configuration import unregister_metric

    # Unregister previously registered metric configuration
    unregister_metric("metric_name")

.. note::

    It will raise ``ImproperlyConfigured`` exception if the concerned
    metric configuration is not registered.

Registering / Unregistering Chart Configuration
-----------------------------------------------

**OpenWISP Monitoring** provides registering and unregistering chart
configuration through utility functions
``openwisp_monitoring.monitoring.configuration.register_chart`` and
``openwisp_monitoring.monitoring.configuration.unregister_chart``. Using
these functions you can register or unregister chart configurations from
anywhere in your code.

``register_chart``
~~~~~~~~~~~~~~~~~~

This function is used to register a new chart configuration from anywhere
in your code.

======================== ===============================================
**Parameter**            **Description**
**chart_name**:          A ``str`` defining name of the chart
                         configuration.
**chart_configuration**: A ``dict`` defining configuration of the chart.
======================== ===============================================

An example usage has been shown below.

.. code-block:: python

    from openwisp_monitoring.monitoring.configuration import register_chart

    # Define configuration of your chart
    chart_config = {
        "type": "histogram",
        "title": "Histogram",
        "description": "Histogram",
        "top_fields": 2,
        "order": 999,
        "query": {
            "influxdb": (
                "SELECT {fields|SUM|/ 1} FROM {key} "
                "WHERE time >= '{time}' AND content_type = "
                "'{content_type}' AND object_id = '{object_id}'"
            )
        },
    }

    # Register your custom chart configuration
    register_chart("chart_name", chart_config)

.. note::

    It will raise ``ImproperlyConfigured`` exception if a chart
    configuration is already registered with same name (not to be confused
    with verbose_name).

If you don't need to register a new chart but need to change a specific
key of an existing chart configuration, you can use
:ref:`OPENWISP_MONITORING_CHARTS <openwisp_monitoring_charts>`.

``unregister_chart``
~~~~~~~~~~~~~~~~~~~~

This function is used to unregister a chart configuration from anywhere in
your code.

=============== ===================================================
**Parameter**   **Description**
**chart_name**: A ``str`` defining name of the chart configuration.
=============== ===================================================

An example usage is shown below.

.. code-block:: python

    from openwisp_monitoring.monitoring.configuration import unregister_chart

    # Unregister previously registered chart configuration
    unregister_chart("chart_name")

.. note::

    It will raise ``ImproperlyConfigured`` exception if the concerned
    chart configuration is not registered.

Monitoring Notifications
------------------------

OpenWISP Monitoring registers and uses the following notification types:

- ``threshold_crossed``: Fires when a metric crosses the boundary defined
  in the threshold value of the alert settings.
- ``threhold_recovery``: Fires when a metric goes back within the expected
  range.
- ``connection_is_working``: Fires when the connection to a device is
  working.
- ``connection_is_not_working``: Fires when the connection (e.g.: SSH) to
  a device stops working (e.g.: credentials are outdated, management IP
  address is outdated, or device is not reachable).

Registering Notification Types
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can define your own notification types using
``register_notification_type`` function from OpenWISP Notifications.

For more information, see the relevant :ref:`documentation section about
registering notification types in the Notifications module
<notifications_register_type>`.

Once a new notification type is registered, you have to use the
:doc:`"notify" signal provided the Notifications module
</notifications/user/sending-notifications>` to send notifications for
this type.

Signals
-------

.. include:: /partials/signals-note.rst

``device_metrics_received``
~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Full Python path**:
``openwisp_monitoring.device.signals.device_metrics_received``

**Arguments**:

- ``instance``: instance of ``Device`` whose metrics have been received
- ``request``: the HTTP request object
- ``time``: time with which metrics will be saved. If none, then server
  time will be used
- ``current``: whether the data has just been collected or was collected
  previously and sent now due to network connectivity issues

This signal is emitted when device metrics are received to the
``DeviceMetric`` view (only when using HTTP POST).

The signal is emitted just before a successful response is returned, it is
not sent if the response was not successful.

``health_status_changed``
~~~~~~~~~~~~~~~~~~~~~~~~~

**Full Python path**:
``openwisp_monitoring.device.signals.health_status_changed``

**Arguments**:

- ``instance``: instance of ``DeviceMonitoring`` whose status has been
  changed
- ``status``: the status by which DeviceMonitoring's existing status has
  been updated with

This signal is emitted only if the health status of DeviceMonitoring
object gets updated.

``threshold_crossed``
~~~~~~~~~~~~~~~~~~~~~

**Full Python path**:
``openwisp_monitoring.monitoring.signals.threshold_crossed``

**Arguments**:

- ``metric``: ``Metric`` object whose threshold defined in related alert
  settings was crossed
- ``alert_settings``: ``AlertSettings`` related to the ``Metric``
- ``target``: related ``Device`` object
- ``first_time``: it will be set to true when the metric is written for
  the first time. It shall be set to false afterwards.
- ``tolerance_crossed``: it will be set to true if the metric has crossed
  the threshold for tolerance configured in alert settings. Otherwise, it
  will be set to false.

``first_time`` parameter can be used to avoid initiating unneeded actions.
For example, sending recovery notifications.

This signal is emitted when the threshold value of a ``Metric`` defined in
alert settings is crossed.

``pre_metric_write``
~~~~~~~~~~~~~~~~~~~~

**Full Python path**:
``openwisp_monitoring.monitoring.signals.pre_metric_write``

**Arguments**:

- ``metric``: ``Metric`` object whose data shall be stored in timeseries
  database
- ``values``: metric data that shall be stored in the timeseries database
- ``time``: time with which metrics will be saved
- ``current``: whether the data has just been collected or was collected
  previously and sent now due to network connectivity issues

This signal is emitted for every metric before the write operation is sent
to the timeseries database.

``post_metric_write``
~~~~~~~~~~~~~~~~~~~~~

**Full Python path**:
``openwisp_monitoring.monitoring.signals.post_metric_write``

**Arguments**:

- ``metric``: ``Metric`` object whose data is being stored in timeseries
  database
- ``values``: metric data that is being stored in the timeseries database
- ``time``: time with which metrics will be saved
- ``current``: whether the data has just been collected or was collected
  previously and sent now due to network connectivity issues

This signal is emitted for every metric after the write operation is
successfully executed in the background.

Exceptions
----------

``TimeseriesWriteException``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Full Python path**:
``openwisp_monitoring.db.exceptions.TimeseriesWriteException``

If there is any failure due while writing data in timeseries database,
this exception will be raised with a helpful error message explaining the
cause of the failure. This exception will normally be caught and the
failed write task will be retried in the background so that there is no
loss of data if failures occur due to overload of Timeseries server. You
can read more about this retry mechanism at
:ref:`OPENWISP_MONITORING_WRITE_RETRY_OPTIONS
<openwisp_monitoring_write_retry_options>`.

``InvalidMetricConfigException``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Full Python path**:
``openwisp_monitoring.monitoring.exceptions.InvalidMetricConfigException``

This exception will be raised if the metric configuration is broken.

``InvalidChartConfigException``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Full Python path**:
``openwisp_monitoring.monitoring.exceptions.InvalidChartConfigException``

This exception will be raised if the chart configuration is broken.
