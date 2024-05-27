Registering / Unregistering Metric Configuration
================================================

.. include:: /partials/developers-docs-warning.rst

**OpenWISP Monitoring** provides registering and unregistering metric
configuration through utility functions
``openwisp_monitoring.monitoring.configuration.register_metric`` and
``openwisp_monitoring.monitoring.configuration.unregister_metric``. Using
these functions you can register or unregister metric configurations from
anywhere in your code.

``register_metric``
-------------------

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
                "title": _("Uptime"),
                "description": _(
                    "A value of 100% means reachable, 0% means unreachable, values in "
                    "between 0% and 100% indicate the average reachability in the "
                    "period observed. Obtained with the fping linux program."
                ),
                "summary_labels": [_("Average uptime")],
                "unit": "%",
                "order": 200,
                "colorscale": {
                    "max": 100,
                    "min": 0,
                    "label": _("Reachable"),
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
                        [100, "#498b26", _("Reachable")],
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
                "email_subject": _(
                    "[{site.name}] {notification.target} is not reachable"
                ),
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
---------------------

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
