Settings
--------

``TIMESERIES_DATABASE``
~~~~~~~~~~~~~~~~~~~~~~~

+--------------+-----------+
| **type**:    | ``str``   |
+--------------+-----------+
| **default**: | see below |
+--------------+-----------+

.. code-block:: python

    TIMESERIES_DATABASE = {
        'BACKEND': 'openwisp_monitoring.db.backends.influxdb',
        'USER': 'openwisp',
        'PASSWORD': 'openwisp',
        'NAME': 'openwisp2',
        'HOST': 'localhost',
        'PORT': '8086',
        'OPTIONS': {
            'udp_writes': False,
            'udp_port': 8089,
        }
    }

The following table describes all keys available in ``TIMESERIES_DATABASE``
setting:

+---------------+--------------------------------------------------------------------------------------+
| **Key**       | ``Description``                                                                      |
+---------------+--------------------------------------------------------------------------------------+
| ``BACKEND``   | The timeseries database backend to use. You can select one of the backends           |
|               | located in ``openwisp_monitoring.db.backends``                                       |
+---------------+--------------------------------------------------------------------------------------+
| ``USER``      | User for logging into the timeseries database                                        |
+---------------+--------------------------------------------------------------------------------------+
| ``PASSWORD``  | Password of the timeseries database user                                             |
+---------------+--------------------------------------------------------------------------------------+
| ``NAME``      | Name of the timeseries database                                                      |
+---------------+--------------------------------------------------------------------------------------+
| ``HOST``      | IP address/hostname of machine where the timeseries database is running              |
+---------------+--------------------------------------------------------------------------------------+
| ``PORT``      | Port for connecting to the timeseries database                                       |
+---------------+--------------------------------------------------------------------------------------+
| ``OPTIONS``   | These settings depends on the timeseries backend:                                    |
|               |                                                                                      |
|               | +-----------------+----------------------------------------------------------------+ |
|               | | ``udp_writes``  | Whether to use UDP for writing data to the timeseries database | |
|               | +-----------------+----------------------------------------------------------------+ |
|               | | ``udp_port``    | Timeseries database port for writing data using UDP            | |
|               | +-----------------+----------------------------------------------------------------+ |
+---------------+--------------------------------------------------------------------------------------+

**Note:** UDP packets can have a maximum size of 64KB. When using UDP for writing timeseries
data, if the size of the data exceeds 64KB, TCP mode will be used instead.

**Note:** If you want to use the ``openwisp_monitoring.db.backends.influxdb`` backend
with UDP writes enabled, then you need to enable two different ports for UDP
(each for different retention policy) in your InfluxDB configuration. The UDP configuration
section of your InfluxDB should look similar to the following:

.. code-block:: text

    # For writing data with the "default" retention policy
    [[udp]]
    enabled = true
    bind-address = "127.0.0.1:8089"
    database = "openwisp2"

    # For writing data with the "short" retention policy
    [[udp]]
    enabled = true
    bind-address = "127.0.0.1:8090"
    database = "openwisp2"
    retention-policy = 'short'

If you are using `ansible-openwisp2 <https://github.com/openwisp/ansible-openwisp2>`_
for deploying OpenWISP, you can set the ``influxdb_udp_mode`` ansible variable to ``true``
in your playbook, this will make the ansible role automatically configure the InfluxDB UDP listeners.
You can refer to the `ansible-ow-influxdb's <https://github.com/openwisp/ansible-ow-influxdb#role-variables>`_
(a dependency of ansible-openwisp2) documentation to learn more.

``OPENWISP_MONITORING_DEFAULT_RETENTION_POLICY``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+--------------------------+
| **type**:    | ``str``                  |
+--------------+--------------------------+
| **default**: | ``26280h0m0s`` (3 years) |
+--------------+--------------------------+

The default retention policy that applies to the timeseries data.

``OPENWISP_MONITORING_SHORT_RETENTION_POLICY``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+-------------+
| **type**:    | ``str``     |
+--------------+-------------+
| **default**: | ``24h0m0s`` |
+--------------+-------------+

The default retention policy used to store raw device data.

This data is only used to assess the recent status of devices, keeping
it for a long time would not add much benefit and would cost a lot more
in terms of disk space.

``OPENWISP_MONITORING_AUTO_PING``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+-------------+
| **type**:    | ``bool``    |
+--------------+-------------+
| **default**: | ``True``    |
+--------------+-------------+

Whether ping checks are created automatically for devices.

``OPENWISP_MONITORING_PING_CHECK_CONFIG``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+-------------+
| **type**:    | ``dict``    |
+--------------+-------------+
| **default**: | ``{}``      |
+--------------+-------------+

This setting allows to override the default ping check configuration defined in
``openwisp_monitoring.check.classes.ping.DEFAULT_PING_CHECK_CONFIG``.

For example, if you want to change only the **timeout** of
``ping`` you can use:

.. code-block:: python

    OPENWISP_MONITORING_PING_CHECK_CONFIG = {
        'timeout': {
            'default': 1000,
        },
    }

If you are overriding the default value for any parameter
beyond the maximum or minimum value defined in
``openwisp_monitoring.check.classes.ping.DEFAULT_PING_CHECK_CONFIG``,
you will also need to override the ``maximum`` or ``minimum`` fields
as following:

.. code-block:: python

    OPENWISP_MONITORING_PING_CHECK_CONFIG = {
        'timeout': {
            'default': 2000,
            'minimum': 1500,
            'maximum': 2500,
        },
    }

**Note:** Above ``maximum`` and ``minimum`` values are only used for
validating custom parameters of a ``Check`` object.

``OPENWISP_MONITORING_AUTO_DEVICE_CONFIG_CHECK``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+-------------+
| **type**:    | ``bool``    |
+--------------+-------------+
| **default**: | ``True``    |
+--------------+-------------+

This setting allows you to choose whether `config_applied <#configuration-applied>`_ checks should be
created automatically for newly registered devices. It's enabled by default.

``OPENWISP_MONITORING_CONFIG_CHECK_INTERVAL``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+-------------+
| **type**:    | ``int``     |
+--------------+-------------+
| **default**: | ``5``       |
+--------------+-------------+

This setting allows you to configure the config check interval used by
`config_applied <#configuration-applied>`_. By default it is set to 5 minutes.

``OPENWISP_MONITORING_AUTO_IPERF3``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+-------------+
| **type**:    | ``bool``    |
+--------------+-------------+
| **default**: | ``False``   |
+--------------+-------------+

This setting allows you to choose whether `iperf3 <#iperf3-1>`_ checks should be
created automatically for newly registered devices. It's disabled by default.

``OPENWISP_MONITORING_IPERF3_CHECK_CONFIG``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+-------------+
| **type**:    | ``dict``    |
+--------------+-------------+
| **default**: | ``{}``      |
+--------------+-------------+

This setting allows to override the default iperf3 check configuration defined in
``openwisp_monitoring.check.classes.iperf3.DEFAULT_IPERF3_CHECK_CONFIG``.

For example, you can change the values of `supported iperf3 check parameters <#iperf3-check-parameters>`_.

.. code-block:: python

   OPENWISP_MONITORING_IPERF3_CHECK_CONFIG = {
       # 'org_pk' : {'host' : [], 'client_options' : {}}
       'a9734710-db30-46b0-a2fc-01f01046fe4f': {
           # Some public iperf3 servers
           # https://iperf.fr/iperf-servers.php#public-servers
           'host': ['iperf3.openwisp.io', '2001:db8::1', '192.168.5.2'],
           'client_options': {
               'port': 6209,
               # Number of parallel client streams to run
               # note that iperf3 is single threaded
               # so if you are CPU bound this will not
               # yield higher throughput
               'parallel': 5,
               # Set the connect_timeout (in milliseconds) for establishing
               # the initial control connection to the server, the lower the value
               # the faster the down iperf3 server will be detected (ex. 1000 ms (1 sec))
               'connect_timeout': 1000,
               # Window size / socket buffer size
               'window': '300K',
               # Only one reverse condition can be chosen,
               # reverse or bidirectional
               'reverse': True,
               # Only one test end condition can be chosen,
               # time, bytes or blockcount
               'blockcount': '1K',
               'udp': {'bitrate': '50M', 'length': '1460K'},
               'tcp': {'bitrate': '20M', 'length': '256K'},
           },
       }
   }

``OPENWISP_MONITORING_IPERF3_CHECK_DELETE_RSA_KEY``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+-------------------------------+
| **type**:    | ``bool``                      |
+--------------+-------------------------------+
| **default**: | ``True``                      |
+--------------+-------------------------------+

This setting allows you to set whether
`iperf3 check RSA public key <#configure-iperf3-check-for-authentication>`_
will be deleted after successful completion of the check or not.

``OPENWISP_MONITORING_IPERF3_CHECK_LOCK_EXPIRE``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+-------------------------------+
| **type**:    | ``int``                       |
+--------------+-------------------------------+
| **default**: | ``600``                       |
+--------------+-------------------------------+

This setting allows you to set a cache lock expiration time for the iperf3 check when
running on multiple servers. Make sure it is always greater than the total iperf3 check
time, i.e. greater than the TCP + UDP test time. By default, it is set to **600 seconds (10 mins)**.

``OPENWISP_MONITORING_AUTO_CHARTS``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+-----------------------------------------------------------------+
| **type**:    | ``list``                                                        |
+--------------+-----------------------------------------------------------------+
| **default**: | ``('traffic', 'wifi_clients', 'uptime', 'packet_loss', 'rtt')`` |
+--------------+-----------------------------------------------------------------+

Automatically created charts.

``OPENWISP_MONITORING_CRITICAL_DEVICE_METRICS``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+-----------------------------------------------------------------+
| **type**:    | ``list`` of ``dict`` objects                                    |
+--------------+-----------------------------------------------------------------+
| **default**: | ``[{'key': 'ping', 'field_name': 'reachable'}]``                |
+--------------+-----------------------------------------------------------------+

Device metrics that are considered critical:

when a value crosses the boundary defined in the "threshold value" field
of the alert settings related to one of these metric types, the health status
of the device related to the metric moves into ``CRITICAL``.

By default, if devices are not reachable by pings they are flagged as ``CRITICAL``.

``OPENWISP_MONITORING_HEALTH_STATUS_LABELS``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+--------------------------------------------------------------------------------------+
| **type**:    | ``dict``                                                                             |
+--------------+--------------------------------------------------------------------------------------+
| **default**: | ``{'unknown': 'unknown', 'ok': 'ok', 'problem': 'problem', 'critical': 'critical'}`` |
+--------------+--------------------------------------------------------------------------------------+

This setting allows to change the health status labels, for example, if we
want to use ``online`` instead of ``ok`` and ``offline`` instead of ``critical``,
you can use the following configuration:

.. code-block:: python

    OPENWISP_MONITORING_HEALTH_STATUS_LABELS = {
        'ok': 'online',
        'problem': 'problem',
        'critical': 'offline'
    }

``OPENWISP_MONITORING_WIFI_SESSIONS_ENABLED``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+-------------+
| **type**:    | ``bool``    |
+--------------+-------------+
| **default**: | ``True``    |
+--------------+-------------+

Setting this to ``False`` will disable `Monitoring Wifi Sessions <#monitoring-wifi-sessions>`_
feature.

``OPENWISP_MONITORING_MANAGEMENT_IP_ONLY``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+-------------+
| **type**:    | ``bool``    |
+--------------+-------------+
| **default**: | ``True``    |
+--------------+-------------+

By default, only the management IP will be used to perform active checks to
the devices.

If the devices are connecting to your OpenWISP instance using a shared layer2
network, hence the OpenWSP server can reach the devices using the ``last_ip``
field, you can set this to ``False``.

**Note:** If this setting is not configured, it will fallback to the value of
`OPENWISP_CONTROLLER_MANAGEMENT_IP_ONLY setting
<https://github.com/openwisp/openwisp-controller#openwisp_controller_management_ip_only>`_.
If ``OPENWISP_CONTROLLER_MANAGEMENT_IP_ONLY`` also not configured,
then it will fallback to ``True``.

``OPENWISP_MONITORING_DEVICE_RECOVERY_DETECTION``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+-------------+
| **type**:    | ``bool``    |
+--------------+-------------+
| **default**: | ``True``    |
+--------------+-------------+

When device recovery detection is enabled, recoveries are discovered as soon as
a device contacts the openwisp system again (eg: to get the configuration checksum
or to send monitoring metrics).

This feature is enabled by default.

If you use OpenVPN as the management VPN, you may want to check out a similar
integration built in **openwisp-network-topology**: when the status of an OpenVPN link
changes (detected by monitoring the status information of OpenVPN), the
network topology module will trigger the monitoring checks.
For more information see:
`Network Topology Device Integration <https://github.com/openwisp/openwisp-network-topology#integration-with-openwisp-controller-and-openwisp-monitoring>`_

``OPENWISP_MONITORING_MAC_VENDOR_DETECTION``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+-------------+
| **type**:    | ``bool``    |
+--------------+-------------+
| **default**: | ``True``    |
+--------------+-------------+

Indicates whether mac addresses will be complemented with hardware vendor
information by performing lookups on the OUI
(Organization Unique Identifier) table.

This feature is enabled by default.

``OPENWISP_MONITORING_WRITE_RETRY_OPTIONS``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+-----------+
| **type**:    | ``dict``  |
+--------------+-----------+
| **default**: | see below |
+--------------+-----------+

.. code-block:: python

    # default value of OPENWISP_MONITORING_RETRY_OPTIONS:

    dict(
        max_retries=None,
        retry_backoff=True,
        retry_backoff_max=600,
        retry_jitter=True,
    )

Retry settings for recoverable failures during metric writes.

By default if a metric write fails (eg: due to excessive load on timeseries database at that moment)
then the operation will be retried indefinitely with an exponential random backoff and a maximum delay of 10 minutes.

This feature makes the monitoring system resilient to temporary outages and helps to prevent data loss.

For more information regarding these settings, consult the `celery documentation
regarding automatic retries for known errors
<https://docs.celeryproject.org/en/stable/userguide/tasks.html#automatic-retry-for-known-exceptions>`_.

**Note:** The retry mechanism does not work when using ``UDP`` for writing
data to the timeseries database. It is due to the nature of ``UDP`` protocol
which does not acknowledge receipt of data packets.

``OPENWISP_MONITORING_TIMESERIES_RETRY_OPTIONS``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+-----------+
| **type**:    | ``dict``  |
+--------------+-----------+
| **default**: | see below |
+--------------+-----------+

.. code-block:: python

    # default value of OPENWISP_MONITORING_RETRY_OPTIONS:

    dict(
        max_retries=6,
        delay=2
    )

On busy systems, communication with the timeseries DB can occasionally fail.
The timeseries DB backend will retry on any exception according to these settings.
The delay kicks in only after the third consecutive attempt.

This setting shall not be confused with ``OPENWISP_MONITORING_WRITE_RETRY_OPTIONS``,
which is used to configure the infinite retrying of the celery task which writes
metric data to the timeseries DB, while ``OPENWISP_MONITORING_TIMESERIES_RETRY_OPTIONS``
deals with any other read/write operation on the timeseries DB which may fail.

However these retries are not handled by celery but are simple python loops,
which will eventually give up if a problem persists.

``OPENWISP_MONITORING_TIMESERIES_RETRY_DELAY``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+-------------+
| **type**:    |   ``int``   |
+--------------+-------------+
| **default**: |    ``2``    |
+--------------+-------------+

This settings allow you to configure the retry delay time (in seconds) after 3 failed attempt in timeseries database.

This retry setting is used in retry mechanism to make the requests to the timeseries database resilient.

This setting is independent of celery retry settings.

``OPENWISP_MONITORING_DASHBOARD_MAP``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+-------------+
| **type**:    | ``bool``    |
+--------------+-------------+
| **default**: | ``True``    |
+--------------+-------------+

Whether the geographic map in the dashboard is enabled or not.
This feature provides a geographic map which shows the locations
which have devices installed in and provides a visual representation
of the monitoring status of the devices, this allows to get
an overview of the network at glance.

This feature is enabled by default and depends on the setting
``OPENWISP_ADMIN_DASHBOARD_ENABLED`` from
`openwisp-utils <https://github.com/openwisp/openwisp-utils>`__
being set to ``True`` (which is the default).

You can turn this off if you do not use the geographic features
of OpenWISP.

``OPENWISP_MONITORING_DASHBOARD_TRAFFIC_CHART``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+--------------------------------------------+
| **type**:    | ``dict``                                   |
+--------------+--------------------------------------------+
| **default**: | ``{'__all__': ['wan', 'eth1', 'eth0.2']}`` |
+--------------+--------------------------------------------+

This settings allows to configure the interfaces which should
be included in the **General Traffic** chart in the admin dashboard.

This setting should be defined in the following format:

.. code-block::python

    OPENWISP_MONITORING_DASHBOARD_TRAFFIC_CHART = {
        '<organization-uuid>': ['<list-of-interfaces>']
    }

E.g., if you want the **General Traffic** chart to show data from
two interfaces for an organization, you need to configure this setting
as follows:

.. code-block::python

    OPENWISP_MONITORING_DASHBOARD_TRAFFIC_CHART = {
        # organization uuid
        'f9601bbd-b6d5-4704-85e3-5851894437bf': ['eth1', 'eth2']
    }

**Note**: The value of ``__all__`` key is used if an organization
does not have list of interfaces defined in ``OPENWISP_MONITORING_DASHBOARD_TRAFFIC_CHART``.

**Note**: If a user can manage more than one organization (e.g. superusers),
then the **General Traffic** chart will always show data from interfaces
of ``__all__`` configuration.

.. _openwisp_monitoring_metrics:

``OPENWISP_MONITORING_METRICS``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+-------------+
| **type**:    | ``dict``    |
+--------------+-------------+
| **default**: | ``{}``      |
+--------------+-------------+

This setting allows to define additional metric configuration or to override
the default metric configuration defined in
``openwisp_monitoring.monitoring.configuration.DEFAULT_METRICS``.

For example, if you want to change only the **field_name** of
``clients`` metric to ``wifi_clients`` you can use:

.. code-block:: python

    from django.utils.translation import gettext_lazy as _

    OPENWISP_MONITORING_METRICS = {
        'clients': {
            'label': _('WiFi clients'),
            'field_name': 'wifi_clients',
        },
    }

For example, if you want to change only the default alert settings of
``memory`` metric you can use:

.. code-block:: python

    OPENWISP_MONITORING_METRICS = {
        'memory': {
            'alert_settings': {'threshold': 75, 'tolerance': 10}
        },
    }

For example, if you want to change only the notification of
``config_applied`` metric you can use:

.. code-block:: python

    from django.utils.translation import gettext_lazy as _

    OPENWISP_MONITORING_METRICS = {
        'config_applied': {
            'notification': {
                'problem': {
                    'verbose_name': 'Configuration PROBLEM',
                    'verb': _('has not been applied'),
                    'email_subject': _(
                        '[{site.name}] PROBLEM: {notification.target} configuration '
                        'status issue'
                    ),
                    'message': _(
                        'The configuration for device [{notification.target}]'
                        '({notification.target_link}) {notification.verb} in a timely manner.'
                    ),
                },
                'recovery': {
                    'verbose_name': 'Configuration RECOVERY',
                    'verb': _('configuration has been applied again'),
                    'email_subject': _(
                        '[{site.name}] RECOVERY: {notification.target} {notification.verb} '
                        'successfully'
                    ),
                    'message': _(
                        'The device [{notification.target}]({notification.target_link}) '
                        '{notification.verb} successfully.'
                    ),
                },
            },
        },
    }

Or if you want to define a new metric configuration, which you can then
call in your custom code (eg: a custom check class), you can do so as follows:

.. code-block:: python

    from django.utils.translation import gettext_lazy as _

    OPENWISP_MONITORING_METRICS = {
        'top_fields_mean': {
            'name': 'Top Fields Mean',
            'key': '{key}',
            'field_name': '{field_name}',
            'label': '_(Top fields mean)',
            'related_fields': ['field1', 'field2', 'field3'],
        },
    }

``OPENWISP_MONITORING_CHARTS``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+-------------+
| **type**:    | ``dict``    |
+--------------+-------------+
| **default**: | ``{}``      |
+--------------+-------------+

This setting allows to define additional charts or to override
the default chart configuration defined in
``openwisp_monitoring.monitoring.configuration.DEFAULT_CHARTS``.

In the following example, we modify the description of the traffic chart:

.. code-block:: python

    OPENWISP_MONITORING_CHARTS = {
        'traffic': {
            'description': (
                'Network traffic, download and upload, measured on '
                'the interface "{metric.key}", custom message here.'
            ),
        }
    }

Or if you want to define a new chart configuration, which you can then
call in your custom code (eg: a custom check class), you can do so as follows:

.. code-block:: python

    from django.utils.translation import gettext_lazy as _

    OPENWISP_MONITORING_CHARTS = {
        'ram': {
            'type': 'line',
            'title': 'RAM usage',
            'description': 'RAM usage',
            'unit': 'bytes',
            'order': 100,
            'query': {
                'influxdb': (
                    "SELECT MEAN(total) AS total, MEAN(free) AS free, "
                    "MEAN(buffered) AS buffered FROM {key} WHERE time >= '{time}' AND "
                    "content_type = '{content_type}' AND object_id = '{object_id}' "
                    "GROUP BY time(1d)"
                )
            },
        }
    }

In case you just want to change the colors used in a chart here's how to do it:

.. code-block:: python

    OPENWISP_MONITORING_CHARTS = {
        'traffic': {
            'colors': ['#000000', '#cccccc', '#111111']
        }
    }

``OPENWISP_MONITORING_DEFAULT_CHART_TIME``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+---------------------+---------------------------------------------+
| **type**:           | ``str``                                     |
+---------------------+---------------------------------------------+
| **default**:        | ``7d``                                      |
+---------------------+---------------------------------------------+
| **possible values** | ``1d``, ``3d``, ``7d``, ``30d`` or ``365d`` |
+---------------------+---------------------------------------------+

Allows to set the default time period of the time series charts.

``OPENWISP_MONITORING_AUTO_CLEAR_MANAGEMENT_IP``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+-------------+
| **type**:    | ``bool``    |
+--------------+-------------+
| **default**: | ``True``    |
+--------------+-------------+

This setting allows you to automatically clear management_ip of a device
when it goes offline. It is enabled by default.

``OPENWISP_MONITORING_API_URLCONF``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+-------------+
| **type**:    | ``string``  |
+--------------+-------------+
| **default**: | ``None``    |
+--------------+-------------+

Changes the urlconf option of django urls to point the monitoring API
urls to another installed module, example, ``myapp.urls``.
(Useful when you have a seperate API instance.)

``OPENWISP_MONITORING_API_BASEURL``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+-------------+
| **type**:    | ``string``  |
+--------------+-------------+
| **default**: | ``None``    |
+--------------+-------------+

If you have a seperate server for API of openwisp-monitoring on a different
domain, you can use this option to change the base of the url, this will
enable you to point all the API urls to your openwisp-monitoring API server's
domain, example: ``https://mymonitoring.myapp.com``.

``OPENWISP_MONITORING_CACHE_TIMEOUT``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+----------------------------------+
| **type**:    | ``int``                          |
+--------------+----------------------------------+
| **default**: | ``86400`` (24 hours in seconds)  |
+--------------+----------------------------------+

This setting allows to configure timeout (in seconds) for monitoring data cache.
