Adaptive size charts
====================

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
