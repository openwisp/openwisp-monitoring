Monitoring WiFi Sessions
========================

OpenWISP Monitoring maintains a record of WiFi sessions created by clients
joined to a radio of managed devices. The WiFi sessions are created
asynchronously from the monitoring data received from the device.

You can filter both currently open sessions and past sessions by their
*start* or *stop* time or *organization* or *group* of the device clients
are connected to or even directly by a *device* name or ID.

.. figure:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/wifi-session-changelist.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/wifi-session-changelist.png
    :align: center

.. figure:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/wifi-session-change.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/wifi-session-change.png
    :align: center

You can disable this feature by configuring
:ref:`OPENWISP_MONITORING_WIFI_SESSIONS_ENABLED
<openwisp_monitoring_wifi_sessions_enabled>` setting.

You can also view open WiFi sessions of a device directly from the
device's change admin under the "WiFi Sessions" tab.

.. figure:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/device-wifi-session-inline.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/device-wifi-session-inline.png
    :align: center

Scheduled Deletion of WiFi Sessions
-----------------------------------

.. important::

    If you have deployed OpenWISP using :doc:`ansible-openwisp2
    </ansible/index>` or :doc:`docker-openwisp </docker/index>`, then this
    feature has been already configured for you. Refer to the
    documentation of your deployment method to know the default value.
    This section is only for reference for users who wish to customize
    OpenWISP, or who have deployed OpenWISP in a different way.

OpenWISP Monitoring provides a celery task to automatically delete WiFi
sessions older than a preconfigured number of days.

The celery task takes only one argument, i.e. number of days. You can
provide any number of days in `args` key while configuring
``CELERY_BEAT_SCHEDULE`` setting.

.. include:: /partials/settings-note.rst

E.g., if you want WiFi Sessions older than 30 days to get deleted
automatically, then configure ``CELERY_BEAT_SCHEDULE`` as follows:

.. code-block:: python

    from datetime import timedelta

    CELERY_BEAT_SCHEDULE.update(
        {
            "delete_wifi_clients_and_sessions": {
                "task": "openwisp_monitoring.monitoring.tasks.delete_wifi_clients_and_sessions",
                "schedule": timedelta(days=1),
                "args": (30,),  # Here we have defined 30 days
            },
        }
    )

Please refer to `"Periodic Tasks" section of Celery's documentation
<https://docs.celeryproject.org/en/stable/userguide/periodic-tasks.html>`_
to learn more.
