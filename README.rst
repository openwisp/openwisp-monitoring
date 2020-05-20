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

* Displays ``Uptime``, ``Memory Status``, ``Load Status``, ``Addresses``, ``Neighbours`` of the **Device**
* Displays ``Monitoring Graphs`` namely ``Uptime``, ``Packet Loss``, ``Round Trip Time``, ``Traffic`` in the form of lively charts
* ``Monitoring Graphs`` can be viewed at resolutions of 1 day, 3 days, a week, a month and a year
* CSV Export of monitoring data
* It allows you to add custom `Charts <https://github.com/openwisp/openwisp-monitoring/#openwisp_monitoring_charts>`_
* It allows to create custom ``Metric``, select a ``Chart`` and set a ``Threshold``
* Notifications are sent whenever ``Threshold`` value is crossed

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
    INFLUXDB_USER = 'openwisp'
    INFLUXDB_PASSWORD = 'openwisp'
    INFLUXDB_DATABASE = 'openwisp2'

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
(threshold value crossed).

Example: CPU usage should be less than 90% but current value is at 95%.

``CRITICAL``
~~~~~~~~~~~~

One of the metrics defined in ``OPENWISP_MONITORING_CRITICAL_DEVICE_METRICS``
has a value which is not in the expected range
(threshold value crossed).

Example: ping is by default a critical metric which is expected to be always 1
(reachable).

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

``OPENWISP_MONITORING_AUTO_GRAPHS``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+-----------------------------------------------------------------+
| **type**:    | ``list``                                                        |
+--------------+-----------------------------------------------------------------+
| **default**: | ``('traffic', 'wifi_clients', 'uptime', 'packet_loss', 'rtt')`` |
+--------------+-----------------------------------------------------------------+

Automatically created graphs.

``OPENWISP_MONITORING_CRITICAL_DEVICE_METRICS``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------+-----------------------------------------------------------------+
| **type**:    | ``list`` of ``dict`` objects                                    |
+--------------+-----------------------------------------------------------------+
| **default**: | ``[{'key': 'ping', 'field_name': 'reachable'}]``                |
+--------------+-----------------------------------------------------------------+

Device metrics that are considered critical: when a threshold related to
one of this type of metric is crossed, the health status of the device related
to the metric moves into ``CRITICAL``.

By default, if devices are not reachable by ping they are flagged as ``CRITICAL``.

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

For example, if you want to change the traffic graph to show
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

    from django.utils.translation import ugettext_lazy as _

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
    SAMPLE_APP=1 ./runtests.py --keepdb --failfast

When running the last line of the previous example, the environment variable
``SAMPLE_APP`` activates the sample apps in ``/tests/openwisp2/``
which are simple django apps that extend ``openwisp-monitoring`` with
the sole purpose of testing its extensibility, for more information regarding
this concept, read the following section.

Extending openwisp-monitoring
-----------------------------

The django apps in ``tests/openwisp2/`` namely ``sample_monitoring``, ``sample_check``,
``sample_device_monitoring`` add some changes on top of the ``openwisp_monitoring`` module
with the sole purpose of testing the module's extensibility.

``sample_monitoring``, ``sample_check`` and ``sample_device_monitoring`` may serve as an example for
extending *openwisp-monitoring* in your own application.

All apps in *openwisp-monitoring* provide a set of models and admin classes which can
be imported, extended and reused by third party apps.

To extend any app in *openwisp-monitoring*, you **MUST NOT** add it to ``settings.INSTALLED_APPS``,
but you must create your own app (which goes into ``settings.INSTALLED_APPS``), import the
base classes from the respective app in ``openwisp-monitoring`` and add your customizations.

In order to help django find the static files and templates of *openwisp-monitoring*,
you need to perform the steps described below.

**Premise**: if you plan on using a customized version of this module,
we suggest to start with it since the beginning, because migrating your data
from the default module to your extended version may be time consuming.

1. Install ``openwisp-monitoring``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Install (and add to the requirement of your project) openwisp-monitoring::

    pip install --U https://github.com/openwisp/openwisp-controller/tarball/master

2. Add ``EXTENDED_APPS``
~~~~~~~~~~~~~~~~~~~~~~~~

Add the following to your ``settings.py``:

.. code-block:: python

    EXTENDED_APPS = ('monitoring', 'check', 'device_monitoring')

3. Add ``openwisp_utils.staticfiles.DependencyFinder``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Add ``openwisp_utils.staticfiles.DependencyFinder`` to
``STATICFILES_FINDERS`` in your ``settings.py``:

.. code-block:: python

    STATICFILES_FINDERS = [
        'django.contrib.staticfiles.finders.FileSystemFinder',
        'django.contrib.staticfiles.finders.AppDirectoriesFinder',
        'openwisp_utils.staticfiles.DependencyFinder',
    ]

4. Add ``openwisp_utils.loaders.DependencyLoader``
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

5. Add swapper configurations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Add the following to your ``settings.py``:

.. code-block:: python

    # Setting models for swapper module
    # For extending ``check`` app
    CHECK_CHECK_MODEL = 'YOUR_MODULE_NAME.Check'
    # For extending ``monitoring`` app
    MONITORING_GRAPH_MODEL = 'YOUR_MODULE_NAME.Graph'
    MONITORING_METRIC_MODEL = 'YOUR_MODULE_NAME.Metric'
    MONITORING_THRESHOLD_MODEL = 'YOUR_MODULE_NAME.Threshold'
    # For extending ``device_monitoring`` app
    DEVICE_MONITORING_DEVICE_MONITORING_MODEL = (
        'YOUR_MODULE_NAME.DeviceMonitoring'
    )

Substitute ``<YOUR_MODULE_NAME>`` with your actual django app name
(also known as ``app_label``).

Extending models
~~~~~~~~~~~~~~~~

To extend ``check`` app, please checkout the `sample_check models.py file <https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/sample_check/models.py>`_.

To extend ``monitoring`` app, please checkout the `sample_monitoring models.py file <https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/sample_monitoring/models.py>`_.

To extend ``device_monitoring`` app, please checkout the `sample_device_monitoring models.py file <https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/sample_device_monitoring/models.py>`_.

Extending the admin
~~~~~~~~~~~~~~~~~~~

To extend ``check`` app, please checkout the `sample_check admin.py file <https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/sample_check/admin.py>`_.

To extend ``monitoring`` app, please checkout the `sample_monitoring admin.py file <https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/sample_monitoring/admin.py>`_.

To extend ``device_monitoring`` app, please checkout the `sample_device_monitoring admin.py file <https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/sample_device_monitoring/admin.py>`_.

Reusing the base tests
~~~~~~~~~~~~~~~~~~~~~~

When developing a custom application based on this module, it's a good
idea to import and run the base tests too,
so that you can be sure the changes you're introducing are not breaking
some of the existing features of openwisp-monitoring.

In case you need to add breaking changes, you can overwrite the tests defined
in the base classes to test your own behavior.

For, extending ``check`` app see the `tests of sample_check app <https://github.com/openwisp/openwisp-monitoring/blob/master/tests/openwisp2/sample_check/tests.py>`_
to find out how to do this.

For, extending ``device_monitoring`` app see the `tests of sample_device_monitoring app <https://github.com/openwisp/openwisp-monitoring/blob/master/tests/openwisp2/sample_device_monitoring/tests.py>`_
to find out how to do this.

For, extending ``monitoring`` app see the `tests of sample_monitoring app <https://github.com/openwisp/openwisp-monitoring/blob/master/tests/openwisp2/sample_monitoring/tests.py>`_
to find out how to do this.

Contributing
------------

Please read the `OpenWISP contributing guidelines
<http://openwisp.io/docs/developer/contributing.html>`_.
