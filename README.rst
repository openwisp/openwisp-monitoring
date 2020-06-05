openwisp-monitoring
===================

.. image:: https://api.travis-ci.org/openwisp/openwisp-monitoring.svg?branch=master
    :target: https://travis-ci.org/github/openwisp/openwisp-monitoring

.. image:: https://coveralls.io/repos/github/openwisp/openwisp-monitoring/badge.svg?branch=master
    :target: https://coveralls.io/github/openwisp/openwisp-monitoring?branch=master

------------

OpenWISP 2 monitoring module (Work in progress).

------------

.. contents:: **Table of Contents**:
   :backlinks: none
   :depth: 3

------------

Available Features
------------------

* Collects and displays device status information like uptime, RAM status, CPU load averages,
  Interface addresses, WiFi interface status and associated clients, Neighbors information, DHCP Leases, Disk/Flash status
* Collection of monitoring information in a timeseries database (currently only influxdb is supported)
* Monitoring charts for uptime, packet loss, round trip time (latency), associated wifi clients, interface traffic,
  RAM usage, CPU load, flash/disk usage
* Charts can be viewed at resolutions of 1 day, 3 days, a week, a month and a year
* CSV Export of monitoring data
* Possibility to define custom `Charts <https://github.com/openwisp/openwisp-monitoring/#openwisp_monitoring_charts>`_
* Extensible active check system: it's possible to write additional checks that
  are run periodically using python classes
* Configurable alerts and web notifications
* API to retrieve the chart metrics and status information of each device

Install Dependencies
--------------------

We use InfluxDB to store metrics and Redis as celery broker (you can use a different
broker if you want). The recommended way for development is running them using Docker
so you will need to `install docker and docker-compose <https://docs.docker.com/engine/install/>`_
beforehand.

In case you prefer not to use Docker you can `install InfluxDB <https://docs.influxdata.com/influxdb/v1.8/introduction/install/>`_
and Redis from your repositories, but keep in mind that the version packaged by your distribution may be different.

Install spatialite and sqlite:

.. code-block:: shell

    sudo apt-get install sqlite3 libsqlite3-dev openssl libssl-dev
    sudo apt-get install gdal-bin libproj-dev libgeos-dev libspatialite-dev

Optionally, install ``fping`` if you need to use the ping active check:

.. code-block:: shell

    sudo apt install -y fping

Setup (integrate in an existing Django project)
-----------------------------------------------

Follow the setup instructions of `openwisp-controller
<https://github.com/openwisp/openwisp-controller>`_, then add the settings described below.

.. code-block:: python

    INSTALLED_APPS = [
        # django apps
        # openwisp2 admin theme (must be loaded here)
        'openwisp_utils.admin_theme',
        # all-auth
        'django.contrib.sites',
        'allauth',
        'allauth.account',
        'allauth.socialaccount',
        'django_extensions',
        # openwisp2 modules
        'openwisp_users',
        'openwisp_controller.pki',
        'openwisp_controller.config',
        'openwisp_controller.connection',
        # monitoring
        'notifications',
        'openwisp_monitoring.monitoring',
        'openwisp_monitoring.device',
        'openwisp_monitoring.check',
        # admin
        'django.contrib.admin',
        'django.forms',
        # other dependencies ...
    ]

    # Make sure you change them in production
    # You can select one of the backends located in openwisp_monitoring.db.backends
    TIMESERIES_DATABASE = {
        'BACKEND': 'openwisp_monitoring.db.backends.influxdb',
        'USER': 'openwisp',
        'PASSWORD': 'openwisp',
        'NAME': 'openwisp2',
        'HOST': 'localhost',
        'PORT': '8086',
    }

``urls.py``:

.. code-block:: python

    from django.conf import settings
    from django.conf.urls import include, url
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

    from openwisp_utils.admin_theme.admin import admin, openwisp_admin

    openwisp_admin()

    urlpatterns = [
        url(r'^admin/', include(admin.site.urls)),
        url(r'', include('openwisp_controller.urls')),
        url(r'', include('openwisp_monitoring.urls')),
    ]

    urlpatterns += staticfiles_urlpatterns()

Add `apptemplates.Loader` to template loaders:

.. code-block:: python

    TEMPLATES = [
        {
            'BACKEND': 'django.template.backends.django.DjangoTemplates',
            'DIRS': [os.path.join(os.path.dirname(BASE_DIR), 'templates')],
            'OPTIONS': {
                'loaders': [
                    'apptemplates.Loader',
                    'django.template.loaders.filesystem.Loader',
                    'django.template.loaders.app_directories.Loader',
                    'openwisp_utils.loaders.DependencyLoader',
                ],
                'context_processors': [
                    'django.template.context_processors.debug',
                    'django.template.context_processors.request',
                    'django.contrib.auth.context_processors.auth',
                    'django.contrib.messages.context_processors.messages',
                ],
            },
        }
    ]

Configure caching (you may use a different cache storage if you want):

.. code-block:: python

    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': 'redis://localhost/0',
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            }
        }
    }

    SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
    SESSION_CACHE_ALIAS = 'default'

Configure celery (you may use a different broker if you want):

.. code-block:: python

    # here we show how to configure celery with redis but you can
    # use other brokers if you want, consult the celery docs
    CELERY_BROKER_URL = 'redis://localhost/1'
    CELERY_BEAT_SCHEDULE = {
        'run_checks': {
            'task': 'openwisp_monitoring.check.tasks.run_check',
            'schedule': timedelta(minutes=5),
        },
    }

    INSTALLED_APPS.append('djcelery_email')
    EMAIL_BACKEND = 'djcelery_email.backends.CeleryEmailBackend'

If you decide to use redis (as shown in these examples),
install the requierd python packages::

    pip install redis django-redis

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

``Available Checks``
--------------------

``Ping``
~~~~~~~~

This check returns information on device ``uptime`` and ``RTT (Round trip time)``.
The Charts ``uptime``, ``packet loss`` and ``rtt`` are created. The ``fping``
command is used to collect these metrics.
You may choose to disable auto creation of this check by setting
`OPENWISP_MONITORING_AUTO_PING <#OPENWISP_MONITORING_AUTO_PING>`_ to ``False``.

Settings
--------

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

``OPENWISP_MONITORING_CHARTS``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+-------------+
| **type**:    | ``dict``    |
+--------------+-------------+
| **default**: | ``{}``      |
+--------------+-------------+

This setting allows to define additional charts or to override
the default chart configuration defined in
``openwisp_monitoring.monitoring.charts.DEFAULT_CHARTS``.

For example, if you want to change the traffic chart to show
MB (megabytes) instead of GB (Gigabytes) you can use:

.. code-block:: python

    OPENWISP_MONITORING_CHARTS = {
        'traffic': {
            'unit': ' MB',
            'description': (
                'Network traffic, download and upload, measured on '
                'the interface "{metric.key}", measured in MB.'
            ),
            'query': {
                'influxdb': (
                    "SELECT SUM(tx_bytes) / 1000000 AS upload, "
                    "SUM(rx_bytes) / 1000000 AS download FROM {key} "
                    "WHERE time >= '{time}' AND content_type = '{content_type}' "
                    "AND object_id = '{object_id}' GROUP BY time(1d)"
                )
            },
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
            'colors': ['#000000', '#cccccc']
        }
    }

``OPENWISP_MONITORING_METRICS``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+-------------+
| **type**:    | ``dict``    |
+--------------+-------------+
| **default**: | ``{}``      |
+--------------+-------------+

This setting allows to define additional metric configuration or to override
the default metric configuration defined in
``openwisp_monitoring.monitoring.metrics.DEFAULT_METRICS``.

For example, if you want to change the field_name of
``clients`` metric to ``wifi_clients`` you can use:

.. code-block:: python

    from django.utils.translation import gettext_lazy as _

    OPENWISP_MONITORING_METRICS = {
        'clients': {
            'label': _('Clients'),
            'key': '{key}',
            'field_name': 'wifi_clients',
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

Registering / Unregistering Chart Configuration
-----------------------------------------------

**OpenWISP Monitoring** provides registering and unregistering chart configuration through utility functions
``openwisp_monitoring.monitoring.charts.register_chart`` and ``openwisp_monitoring.monitoring.charts.unregister_chart``.
Using these functions you can register or unregister chart configurations from anywhere in your code.

register_chart
~~~~~~~~~~~~~~

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

    from openwisp_monitoring.monitoring import register_chart

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

unregister_chart
~~~~~~~~~~~~~~~~

This function is used to unregister a chart configuration from anywhere in your code.

+------------------+-----------------------------------------------------+
|  **Parameter**   |                   **Description**                   |
+------------------+-----------------------------------------------------+
|  **chart_name**: | A ``str`` defining name of the chart configuration. |
+------------------+-----------------------------------------------------+

An example usage is shown below.

.. code-block:: python

    from openwisp_monitoring.monitoring import unregister_chart

    # Unregister previously registered chart configuration
    unregister_chart('chart_name')

**Note**: It will raise ``ImproperlyConfigured`` exception if the concerned chart
configuration is not registered.

Signals
-------

``device_metrics_received``
~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Path**: ``openwisp_monitoring.device.signals.device_metrics_received``

**Arguments**:

- ``instance``: instance of ``Device`` whose metrics have been received
- ``request``: the HTTP request object

This signal is emitted when device metrics are received to the ``DeviceMetric``
view (only when using HTTP POST).

The signal is emitted just before a successful response is returned,
it is not sent if the response was not successful.

``threshold_crossed``
~~~~~~~~~~~~~~~~~~~~~

**Path**: ``openwisp_monitoring.monitoring.signals.threshold_crossed``

**Arguments**:

- ``sender``: Metric class
- ``metric``: ``Metric`` object whose threshold defined in related alert settings was crossed
- ``alert_settings``: ``AlertSettings`` related to the ``Metric``
- ``target``: related ``Device`` object
- ``first_time``: it will be set to true when the metric is written for the first time. It shall be set to false afterwards.

``first_time`` parameter can be used to avoid initiating unneeded actions.
For example, sending recovery notifications.

This signal is emitted when the threshold value of a ``Metric`` defined in
alert settings is crossed.

Default Alerts / Notifications
------------------------------

+-------------------------------+------------------------------------------------------------------+
| Notification Type             | Use                                                              |
+-------------------------------+------------------------------------------------------------------+
| ``threshold_crossed``         | Fires when a metric crosses the boundary defined in the          |
|                               | threshold value of the alert settings.                           |
+-------------------------------+------------------------------------------------------------------+
| ``threshold_recovery``        | Fires when a metric goes back within the expected range.         |
+-------------------------------+------------------------------------------------------------------+
| ``connection_is_working``     | Fires when the connection to a device is working.                |
+-------------------------------+------------------------------------------------------------------+
| ``connection_is_not_working`` | Fires when the connection (eg: SSH) to a device stops working    |
|                               | (eg: credentials are outdated, management IP address is          |
|                               | outdated, or device is not reachable).                           |
+-------------------------------+------------------------------------------------------------------+

Installing for development
--------------------------

Install your forked repo:

.. code-block:: shell

    git clone git://github.com/<your_fork>/openwisp-monitoring
    cd openwisp-monitoring/
    python setup.py develop

Install test requirements:

.. code-block:: shell

    pip install -r requirements-test.txt

Start Redis and InfluxDB using docker-compose:

.. code-block:: shell

    docker-compose up -d

Create the Django database:

.. code-block:: shell

    cd tests/
    ./manage.py migrate
    ./manage.py createsuperuser

Launch development server:

.. code-block:: shell

    ./manage.py runserver 0.0.0.0:8000

You can access the admin interface at http://127.0.0.1:8000/admin/.

Run celery and celery-beat with the following commands
(separate terminal windows are needed):

.. code-block:: shell

    # (cd tests)
    celery -A openwisp2 worker -l info
    celery -A openwisp2 beat -l info

Run tests with:

.. code-block:: shell

    # run qa checks
    ./run-qa-checks

    # standard tests
    ./runtests.py

    # tests for the sample app
    SAMPLE_APP=1 ./runtests.py

When running the last line of the previous example, the environment variable
``SAMPLE_APP`` activates the sample apps in ``/tests/openwisp2/``
which are simple django apps that extend ``openwisp-monitoring`` with
the sole purpose of testing its extensibility, for more information regarding
this concept, read the following section.

Extending openwisp-monitoring
-----------------------------

One of the core values of the OpenWISP project is `Software Reusability <http://openwisp.io/docs/general/values.html#software-reusability-means-long-term-sustainability>`_,
for this reason *openwisp-monitoring* provides a set of base classes
which can be imported, extended and reused to create derivative apps.

In order to implement your custom version of *openwisp-monitoring*,
you need to perform the steps described in the rest of this section.

When in doubt, the code in the `test project <https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/>`_
and the ``sample apps`` namely `sample_check <https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/sample_check/>`_,
`sample_monitoring <https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/sample_monitoring/>`_, `sample_device_monitoring <https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/sample_device_monitoring/>`_
will guide you in the correct direction:
just replicate and adapt that code to get a basic derivative of
*openwisp-monitoring* working.

**Premise**: if you plan on using a customized version of this module,
we suggest to start with it since the beginning, because migrating your data
from the default module to your extended version may be time consuming.

1. Initialize your custom module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The first thing you need to do in order to extend any *openwisp-monitoring* app is create
a new django app which will contain your custom version of that *openwisp-monitoring* app.

A django app is nothing more than a
`python package <https://docs.python.org/3/tutorial/modules.html#packages>`_
(a directory of python scripts), in the following examples we'll call these django apps as
``mycheck``, ``mydevicemonitoring``, ``mymonitoring`` but you can name it how you want::

    django-admin startapp mycheck
    django-admin startapp mydevicemonitoring
    django-admin startapp mymonitoring

Keep in mind that the command mentioned above must be called from a directory
which is available in your `PYTHON_PATH <https://docs.python.org/3/using/cmdline.html#envvar-PYTHONPATH>`_
so that you can then import the result into your project.

Now you need to add ``mycheck`` to ``INSTALLED_APPS`` in your ``settings.py``,
ensuring also that ``openwisp_monitoring.check`` has been removed:

.. code-block:: python

    INSTALLED_APPS = [
        # ... other apps ...
        # 'openwisp_monitoring.check',        <-- comment out or delete this line
        # 'openwisp_monitoring.device',       <-- comment out or delete this line
        # 'openwisp_monitoring.monitoring'    <-- comment out or delete this line
        'mycheck',
        'mydevicemonitoring',
        'mymonitoring',
    ]

For more information about how to work with django projects and django apps,
please refer to the `django documentation <https://docs.djangoproject.com/en/dev/intro/tutorial01/>`_.

2. Install ``openwisp-monitoring``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Install (and add to the requirement of your project) *openwisp-monitoring*::

    pip install --U https://github.com/openwisp/openwisp-monitoring/tarball/master

3. Add ``EXTENDED_APPS``
~~~~~~~~~~~~~~~~~~~~~~~~

Add the following to your ``settings.py``:

.. code-block:: python

    EXTENDED_APPS = ['device_monitoring', 'monitoring', 'check']

4. Add ``openwisp_utils.staticfiles.DependencyFinder``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Add ``openwisp_utils.staticfiles.DependencyFinder`` to
``STATICFILES_FINDERS`` in your ``settings.py``:

.. code-block:: python

    STATICFILES_FINDERS = [
        'django.contrib.staticfiles.finders.FileSystemFinder',
        'django.contrib.staticfiles.finders.AppDirectoriesFinder',
        'openwisp_utils.staticfiles.DependencyFinder',
    ]

5. Add ``openwisp_utils.loaders.DependencyLoader``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Add ``openwisp_utils.loaders.DependencyLoader`` to ``TEMPLATES`` in your ``settings.py``:

.. code-block:: python

    TEMPLATES = [
        {
            'BACKEND': 'django.template.backends.django.DjangoTemplates',
            'OPTIONS': {
                'loaders': [
                    'django.template.loaders.filesystem.Loader',
                    'django.template.loaders.app_directories.Loader',
                    'openwisp_utils.loaders.DependencyLoader',
                ],
                'context_processors': [
                    'django.template.context_processors.debug',
                    'django.template.context_processors.request',
                    'django.contrib.auth.context_processors.auth',
                    'django.contrib.messages.context_processors.messages',
                ],
            },
        }
    ]

6. Inherit the AppConfig class
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Please refer to the following files in the sample app of the test project:

- `sample_check/__init__.py <https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/sample_check/__init__.py>`_.
- `sample_check/apps.py <https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/sample_check/apps.py>`_.
- `sample_monitoring/__init__.py <https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/sample_monitoring/__init__.py>`_.
- `sample_monitoring/apps.py <https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/sample_monitoring/apps.py>`_.
- `sample_device_monitoring/__init__.py <https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/sample_device_monitoring/__init__.py>`_.
- `sample_device_monitoring/apps.py <https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/sample_device_monitoring/apps.py>`_.

For more information regarding the concept of ``AppConfig`` please refer to
the `"Applications" section in the django documentation <https://docs.djangoproject.com/en/dev/ref/applications/>`_.

7. Create your custom models
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To extend ``check`` app, refer to `sample_check models.py file <https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/sample_check/models.py>`_.

To extend ``monitoring`` app, refer to `sample_monitoring models.py file <https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/sample_monitoring/models.py>`_.

To extend ``device_monitoring`` app, refer to `sample_device_monitoring models.py file <https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/sample_device_monitoring/models.py>`_.

**Note**:

- For doubts regarding how to use, extend or develop models please refer to
  the `"Models" section in the django documentation <https://docs.djangoproject.com/en/dev/topics/db/models/>`_.
- For doubts regarding proxy models please refer to `proxy models <https://docs.djangoproject.com/en/dev/topics/db/models/#proxy-models>`_.

8. Add swapper configurations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Add the following to your ``settings.py``:

.. code-block:: python

    # Setting models for swapper module
    # For extending check app
    CHECK_CHECK_MODEL = 'YOUR_MODULE_NAME.Check'
    # For extending monitoring app
    MONITORING_CHART_MODEL = 'YOUR_MODULE_NAME.Chart'
    MONITORING_METRIC_MODEL = 'YOUR_MODULE_NAME.Metric'
    MONITORING_ALERTSETTINGS_MODEL = 'YOUR_MODULE_NAME.AlertSettings'
    # For extending device_monitoring app
    DEVICE_MONITORING_DEVICEDATA_MODEL = 'YOUR_MODULE_NAME.DeviceData'
    DEVICE_MONITORING_DEVICEMONITORING_MODEL = 'YOUR_MODULE_NAME.DeviceMonitoring'

Substitute ``<YOUR_MODULE_NAME>`` with your actual django app name
(also known as ``app_label``).

9. Create database migrations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Create and apply database migrations::

    ./manage.py makemigrations
    ./manage.py migrate

For more information, refer to the
`"Migrations" section in the django documentation <https://docs.djangoproject.com/en/dev/topics/migrations/>`_.

10. Create your custom admin
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To extend ``check`` app, refer to `sample_check admin.py file <https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/sample_check/admin.py>`_.

To extend ``monitoring`` app, refer to `sample_monitoring admin.py file <https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/sample_monitoring/admin.py>`_.

To extend ``device_monitoring`` app, refer to `sample_device_monitoring admin.py file <https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/sample_device_monitoring/admin.py>`_.

To introduce changes to the admin, you can do it in the two ways described below.

**Note**: for doubts regarding how the django admin works, or how it can be customized,
please refer to `"The django admin site" section in the django documentation <https://docs.djangoproject.com/en/dev/ref/contrib/admin/>`_.

1. Monkey patching
##################

If the changes you need to add are relatively small, you can resort to monkey patching.

For example, for ``check`` app you can do it as:

.. code-block:: python

    from openwisp_monitoring.check.admin import CheckAdmin

    CheckAdmin.list_display.insert(1, 'my_custom_field')
    CheckAdmin.ordering = ['-my_custom_field']

Similarly for ``device_monitoring`` app, you can do it as:

.. code-block:: python

    from openwisp_monitoring.device.admin import DeviceAdmin

    DeviceAdmin.list_display.insert(1, 'my_custom_field')
    DeviceAdmin.ordering = ['-my_custom_field']

Similarly for ``monitoring`` app, you can do it as:

.. code-block:: python

    from openwisp_monitoring.monitoring.admin import MetricAdmin, AlertSettingsAdmin

    MetricAdmin.list_display.insert(1, 'my_custom_field')
    MetricAdmin.ordering = ['-my_custom_field']
    AlertSettingsAdmin.list_display.insert(1, 'my_custom_field')
    AlertSettingsAdmin.ordering = ['-my_custom_field']

2. Inheriting admin classes
###########################

If you need to introduce significant changes and/or you don't want to resort to
monkey patching, you can proceed as follows:

For ``check`` app,

.. code-block:: python

    from django.contrib import admin

    from openwisp_monitoring.check.admin import CheckAdmin as BaseCheckAdmin
    from swapper import load_model

    Check = load_model('Check')

    admin.site.unregister(Check)

    @admin.register(Check)
    class CheckAdmin(BaseCheckAdmin):
        # add your changes here

For ``device_monitoring`` app,

.. code-block:: python

    from django.contrib import admin

    from openwisp_monitoring.device_monitoring.admin import DeviceAdmin as BaseDeviceAdmin
    from openwisp_controller.config.models import Device

    admin.site.unregister(Device)

    @admin.register(Device)
    class DeviceAdmin(BaseDeviceAdmin):
        # add your changes here

For ``monitoring`` app,

.. code-block:: python

    from django.contrib import admin

    from openwisp_monitoring.monitoring.admin import (
        AlertSettingsAdmin as BaseAlertSettingsAdmin,
        MetricAdmin as BaseMetricAdmin
    )
    from swapper import load_model

    Metric = load_model('Metric')
    AlertSettings = load_model('AlertSettings')

    admin.site.unregister(Metric)
    admin.site.unregister(AlertSettings)

    @admin.register(Metric)
    class MetricAdmin(BaseMetricAdmin):
        # add your changes here

    @admin.register(AlertSettings)
    class AlertSettingsAdmin(BaseAlertSettingsAdmin):
        # add your changes here

11. Create root URL configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Please refer to the `urls.py <https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/urls.py>`_
file in the test project.

For more information about URL configuration in django, please refer to the
`"URL dispatcher" section in the django documentation <https://docs.djangoproject.com/en/dev/topics/http/urls/>`_.

12. Create celery.py
~~~~~~~~~~~~~~~~~~~~

Please refer to the `celery.py <https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/celery.py>`_
file in the test project.

For more information about the usage of celery in django, please refer to the
`"First steps with Django" section in the celery documentation <https://docs.celeryproject.org/en/master/django/first-steps-with-django.html>`_.

13. Import Celery Tasks
~~~~~~~~~~~~~~~~~~~~~~~

Add the following in your settings.py to import celery tasks from ``device_monitoring`` app.

.. code-block:: python

    CELERY_IMPORTS = ('openwisp_monitoring.device.tasks',)

14. Create the custom command ``run_checks``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Please refer to the `run_checks.py <https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/sample_check/management/commands/run_checks.py>`_
file in the test project.

For more information about the usage of custom management commands in django, please refer to the
`"Writing custom django-admin commands" section in the django documentation <https://docs.djangoproject.com/en/dev/howto/custom-management-commands/>`_.

15. Import the automated tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When developing a custom application based on this module, it's a good idea
to import and run the base tests too, so that you can be sure the changes you're introducing
are not breaking some of the existing features of openwisp-monitoring.

In case you need to add breaking changes, you can overwrite the tests defined
in the base classes to test your own behavior.

For, extending ``check`` app see the `tests of sample_check app <https://github.com/openwisp/openwisp-monitoring/blob/master/tests/openwisp2/sample_check/tests.py>`_
to find out how to do this.

For, extending ``device_monitoring`` app see the `tests of sample_device_monitoring app <https://github.com/openwisp/openwisp-monitoring/blob/master/tests/openwisp2/sample_device_monitoring/tests.py>`_
to find out how to do this.

For, extending ``monitoring`` app see the `tests of sample_monitoring app <https://github.com/openwisp/openwisp-monitoring/blob/master/tests/openwisp2/sample_monitoring/tests.py>`_
to find out how to do this.

Other base classes that can be inherited and extended
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**The following steps are not required and are intended for more advanced customization.**

``DeviceMetricView``
####################

This view is responsible for displaying ``Charts`` and ``Status`` primarily.

The full python path is: ``openwisp_monitoring.device.api.views.DeviceMetricView``.

If you want to extend this view, you will have to perform the additional steps below.

**Step 1. Import and extend view:**

.. code-block:: python

    # mydevice/api/views.py
    from openwisp_monitoring.device.api.views import (
        DeviceMetricView as BaseDeviceMetricView
    )

    class DeviceMetricView(BaseDeviceMetricView):
        # add your customizations here ...
        pass

**Step 2: remove the following line from your root ``urls.py`` file:**

.. code-block:: python

    url(
        r'^api/v1/monitoring/device/(?P<pk>[^/]+)/$',
        views.device_metric,
        name='api_device_metric',
    ),

**Step 3: add an URL route pointing to your custom view in ``urls.py`` file:**

.. code-block:: python

    # urls.py
    from mydevice.api.views import DeviceMetricView

    urlpatterns = [
        # ... other URLs
        url(r'^(?P<path>.*)$', DeviceMetricView.as_view(), name='api_device_metric',),
    ]

Registering new notification types
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can define your own notification types using ``register_notification_type`` function from OpenWISP
Notifications. For more information, see the relevant `openwisp-notifications section about registering notification types
<https://github.com/openwisp/openwisp-notifications#registering--unregistering-notification-types>`_.

Once a new notification type is registered, you have to use the `"notify" signal provided in
openwisp-notifications <https://github.com/openwisp/openwisp-notifications#sending-notifications>`_
to send notifications for this type.

Contributing
------------

Please refer to the `OpenWISP contributing guidelines <http://openwisp.io/docs/developer/contributing.html>`_.
