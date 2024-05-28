Registering / Unregistering Chart Configuration
===============================================

.. include:: /partials/developers-docs-warning.rst

**OpenWISP Monitoring** provides registering and unregistering chart
configuration through utility functions
``openwisp_monitoring.monitoring.configuration.register_chart`` and
``openwisp_monitoring.monitoring.configuration.unregister_chart``. Using
these functions you can register or unregister chart configurations from
anywhere in your code.

``register_chart``
------------------

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

Adaptive size charts
~~~~~~~~~~~~~~~~~~~~

.. figure:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/1.1/adaptive-chart.png
    :align: center

When configuring charts, it is possible to flag their unit as
``adaptive_prefix``, this allows to make the charts more readable because
the units are shown in either `K`, `M`, `G` and `T` depending on the size
of each point, the summary values and Y axis are also resized.

Example taken from the default configuration of the traffic chart:

.. code-block:: python

    OPENWISP_MONITORING_CHARTS = {
        "traffic": {
            # other configurations for this chart
            # traffic measured in 'B' (bytes)
            # unit B, KB, MB, GB, TB
            "unit": "adaptive_prefix+B",
        },
        "bandwidth": {
            # other configurations for this chart
            # adaptive unit for bandwidth related charts
            # bandwidth measured in 'bps'(bits/sec)
            # unit bps, Kbps, Mbps, Gbps, Tbps
            "unit": "adaptive_prefix+bps",
        },
    }

``unregister_chart``
--------------------

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
