Registering / Unregistering Chart Configuration
-----------------------------------------------

**OpenWISP Monitoring** provides registering and unregistering chart configuration through utility functions
``openwisp_monitoring.monitoring.configuration.register_chart`` and ``openwisp_monitoring.monitoring.configuration.unregister_chart``.
Using these functions you can register or unregister chart configurations from anywhere in your code.

``register_chart``
~~~~~~~~~~~~~~~~~~

This function is used to register a new chart configuration from anywhere in your code.

+--------------------------+-----------------------------------------------------+
|      **Parameter**       |                   **Description**                   |
+--------------------------+-----------------------------------------------------+
|      **chart_name**:     | A ``str`` defining name of the chart configuration. |
+--------------------------+-----------------------------------------------------+
| **chart_configuration**: | A ``dict`` defining configuration of the chart.     |
+--------------------------+-----------------------------------------------------+

An example usage has been shown below.

.. code-block:: python

    from openwisp_monitoring.monitoring.configuration import register_chart

    # Define configuration of your chart
    chart_config = {
        'type': 'histogram',
        'title': 'Histogram',
        'description': 'Histogram',
        'top_fields': 2,
        'order': 999,
        'query': {
            'influxdb': (
                "SELECT {fields|SUM|/ 1} FROM {key} "
                "WHERE time >= '{time}' AND content_type = "
                "'{content_type}' AND object_id = '{object_id}'"
            )
        },
    }

    # Register your custom chart configuration
    register_chart('chart_name', chart_config)

**Note**: It will raise ``ImproperlyConfigured`` exception if a chart configuration
is already registered with same name (not to be confused with verbose_name).

If you don't need to register a new chart but need to change a specific key of an
existing chart configuration, you can use :ref:`OPENWISP_MONITORING_CHARTS <openwisp_monitoring_charts>`.

``unregister_chart``
~~~~~~~~~~~~~~~~~~~~

This function is used to unregister a chart configuration from anywhere in your code.

+------------------+-----------------------------------------------------+
|  **Parameter**   |                   **Description**                   |
+------------------+-----------------------------------------------------+
|  **chart_name**: | A ``str`` defining name of the chart configuration. |
+------------------+-----------------------------------------------------+

An example usage is shown below.

.. code-block:: python

    from openwisp_monitoring.monitoring.configuration import unregister_chart

    # Unregister previously registered chart configuration
    unregister_chart('chart_name')

**Note**: It will raise ``ImproperlyConfigured`` exception if the concerned chart
configuration is not registered.
