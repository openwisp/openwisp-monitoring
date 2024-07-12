openwisp-monitoring
===================

.. image:: https://github.com/openwisp/openwisp-monitoring/workflows/OpenWISP%20Monitoring%20CI%20Build/badge.svg?branch=master
    :target: https://github.com/openwisp/openwisp-monitoring/actions?query=workflow%3A%22OpenWISP+Monitoring+CI+Build%22
    :alt: CI build status

.. image:: https://coveralls.io/repos/github/openwisp/openwisp-monitoring/badge.svg?branch=master
    :target: https://coveralls.io/github/openwisp/openwisp-monitoring?branch=master
    :alt: Test coverage

.. image:: https://img.shields.io/librariesio/github/openwisp/openwisp-monitoring
   :target: https://libraries.io/github/openwisp/openwisp-monitoring#repository_dependencies
   :alt: Dependency monitoring

.. image:: https://badge.fury.io/py/openwisp-monitoring.svg
    :target: http://badge.fury.io/py/openwisp-monitoring
    :alt: pypi

.. image:: https://pepy.tech/badge/openwisp-monitoring
   :target: https://pepy.tech/project/openwisp-monitoring
   :alt: downloads

.. image:: https://img.shields.io/gitter/room/nwjs/nw.js.svg?style=flat-square
   :target: https://gitter.im/openwisp/monitoring
   :alt: support chat

.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
   :target: https://pypi.org/project/black/
   :alt: code style: black

.. image:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/monitoring-demo.gif
   :target: https://github.com/openwisp/openwisp-monitoring/tree/docs/docs/monitoring-demo.gif
   :alt: Feature Highlights

------------

**Need a quick overview?** `Try the OpenWISP Demo <https://openwisp.org/demo.html>`_.

OpenWISP Monitoring is a network monitoring system written in Python and Django,
designed to be **extensible**, **programmable**, **scalable** and easy to use by end users:
once the system is configured, monitoring checks, alerts and metric collection
happens automatically.

See the `available features <#available-features>`_.

`OpenWISP <http://openwisp.org>`_ is not only an application designed for end users,
but can also be used as a framework on which custom network automation solutions can be
built on top of its building blocks.

Other popular building blocks that are part of the OpenWISP ecosystem are:

- `openwisp-controller <https://github.com/openwisp/openwisp-controller>`_:
  network and WiFi controller: provisioning, configuration management,
  x509 PKI management and more; works on OpenWRT, but designed to work also on other systems.
- `openwisp-network-topology <https://github.com/openwisp/openwisp-network-topology>`_:
  provides way to collect and visualize network topology data from
  dynamic mesh routing daemons or other network software (eg: OpenVPN);
  it can be used in conjunction with openwisp-monitoring to get a better idea
  of the state of the network
- `openwisp-firmware-upgrader <https://github.com/openwisp/openwisp-firmware-upgrader>`_:
  automated firmware upgrades (single device or mass network upgrades)
- `openwisp-radius <https://github.com/openwisp/openwisp-radius>`_:
  based on FreeRADIUS, allows to implement network access authentication systems like
  802.1x WPA2 Enterprise, captive portal authentication, Hotspot 2.0 (802.11u)
- `openwisp-ipam <https://github.com/openwisp/openwisp-ipam>`_:
  it allows to manage the IP address space of networks

**For a more complete overview of the OpenWISP modules and architecture**,
see the
`OpenWISP Architecture Overview
<https://openwisp.io/docs/general/architecture.html>`_.

.. figure:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/dashboard.png
  :align: center

Available Features
------------------

* Collection of monitoring information in a timeseries database (currently only influxdb is supported)
* Allows to browse alerts easily from the user interface with one click
* Collects and displays `device status <#device-status>`_ information like
  uptime, RAM status, CPU load averages,
  Interface properties and addresses, WiFi interface status and associated clients,
  Neighbors information, DHCP Leases, Disk/Flash status
* Monitoring charts for `ping success rate <#ping>`_, `packet loss <#ping>`_,
  `round trip time (latency) <#ping>`_,
  `associated wifi clients <#wifi-clients>`_, `interface traffic <#traffic>`_,
  `RAM usage <#memory-usage>`_, `CPU load <#cpu-load>`_, `flash/disk usage <#disk-usage>`_,
  mobile signal (LTE/UMTS/GSM `signal strength <#mobile-signal-strength>`_,
  `signal quality <#mobile-signal-quality>`_,
  `access technology in use <#mobile-access-technology-in-use>`_), `bandwidth <#iperf3>`_,
  `transferred data <#iperf3>`_, `restransmits <#iperf3>`_, `jitter <#iperf3>`_,
  `datagram <#iperf3>`_, `datagram loss <#iperf3>`_
* Maintains a record of `WiFi sessions <#monitoring-wifi-sessions>`_ with clients'
  MAC address and vendor, session start and stop time and connected device
  along with other information
* Charts can be viewed at resolutions of the last 1 day, 3 days, 7 days, 30 days, and 365 days
* Configurable alerts
* CSV Export of monitoring data
* An overview of the status of the network is shown in the admin dashboard,
  a chart shows the percentages of devices which are online, offline or having issues;
  there are also `two timeseries charts which show the total unique WiFI clients and
  the traffic flowing to the network <dashboard-monitoring-charts>`_,
  a geographic map is also available for those who use the geographic features of OpenWISP
* Possibility to configure additional `Metrics <#openwisp_monitoring_metrics>`_ and `Charts <#openwisp_monitoring_charts>`_
* Extensible active check system: it's possible to write additional checks that
  are run periodically using python classes
* Extensible metrics and charts: it's possible to define new metrics and new charts
* API to retrieve the chart metrics and status information of each device
  based on `NetJSON DeviceMonitoring <http://netjson.org/docs/what.html#devicemonitoring>`_
* `Iperf3 check <#iperf3-1>`_ that provides network performance measurements such as maximum
  achievable bandwidth, jitter, datagram loss etc of the openwrt device using `iperf3 utility <https://iperf.fr/>`_

------------

.. contents:: **Table of Contents**:
   :backlinks: none
   :depth: 3

------------

Installation instructions
-------------------------

Deploy it in production
~~~~~~~~~~~~~~~~~~~~~~~

See:

- `ansible-openwisp2 <https://github.com/openwisp/ansible-openwisp2>`_
- `docker-openwisp <https://github.com/openwisp/docker-openwisp>`_

Install system dependencies
~~~~~~~~~~~~~~~~~~~~~~~~~~~

*openwisp-monitoring* uses InfluxDB to store metrics. Follow the
`installation instructions from InfluxDB's official documentation <https://docs.influxdata.com/influxdb/v1.8/introduction/install/>`_.

**Note:** Only *InfluxDB 1.8.x* is supported in *openwisp-monitoring*.

Install system packages:

.. code-block:: shell

    sudo apt install -y openssl libssl-dev \
                        gdal-bin libproj-dev libgeos-dev \
                        fping

Install stable version from PyPI
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Install from PyPI:

.. code-block:: shell

    pip install openwisp-monitoring

Install development version
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Install tarball:

.. code-block:: shell

    pip install https://github.com/openwisp/openwisp-monitoring/tarball/master

Alternatively, you can install via pip using git:

.. code-block:: shell

    pip install -e git+git://github.com/openwisp/openwisp-monitoring#egg=openwisp_monitoring

If you want to contribute, follow the instructions in
`"Installing for development" <#installing-for-development>`_ section.

Installing for development
~~~~~~~~~~~~~~~~~~~~~~~~~~

Install the system dependencies as mentioned in the
`"Install system dependencies" <#install-system-dependencies>`_ section.
Install these additional packages that are required for development:

.. code-block:: shell

    sudo apt install -y sqlite3 libsqlite3-dev \
                        libspatialite-dev libsqlite3-mod-spatialite \
                        chromium

Fork and clone the forked repository:

.. code-block:: shell

    git clone git://github.com/<your_fork>/openwisp-monitoring

Navigate into the cloned repository:

.. code-block:: shell

    cd openwisp-monitoring/

Start Redis and InfluxDB using Docker:

.. code-block:: shell

    docker-compose up -d redis influxdb

Setup and activate a virtual-environment. (we'll be using  `virtualenv <https://pypi.org/project/virtualenv/>`_)

.. code-block:: shell

    python -m virtualenv env
    source env/bin/activate

Make sure that you are using pip version 20.2.4 before moving to the next step:

.. code-block:: shell

    pip install -U pip wheel setuptools

Install development dependencies:

.. code-block:: shell

    pip install -e .
    pip install -r requirements-test.txt
    npm install -g jshint stylelint

Install WebDriver for Chromium for your browser version from `<https://chromedriver.chromium.org/home>`_
and extract ``chromedriver`` to one of directories from your ``$PATH`` (example: ``~/.local/bin/``).

Create database:

.. code-block:: shell

    cd tests/
    ./manage.py migrate
    ./manage.py createsuperuser

Run celery and celery-beat with the following commands (separate terminal windows are needed):

.. code-block:: shell

    cd tests/
    celery -A openwisp2 worker -l info
    celery -A openwisp2 beat -l info

Launch development server:

.. code-block:: shell

    ./manage.py runserver 0.0.0.0:8000

You can access the admin interface at http://127.0.0.1:8000/admin/.

Run tests with:

.. code-block:: shell

    ./runtests.py  # using --parallel is not supported in this module

Run quality assurance tests with:

.. code-block:: shell

    ./run-qa-checks

Install and run on docker
~~~~~~~~~~~~~~~~~~~~~~~~~

**Note**: This Docker image is for development purposes only.
For the official OpenWISP Docker images, see: `docker-openwisp
<https://github.com/openwisp/docker-openwisp>`_.

Build from the Dockerfile:

.. code-block:: shell

    docker-compose build

Run the docker container:

.. code-block:: shell

    docker-compose up

Setup (integrate in an existing Django project)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Follow the setup instructions of `openwisp-controller
<https://github.com/openwisp/openwisp-controller>`_, then add the settings described below.

.. code-block:: python

    INSTALLED_APPS = [
        # django apps
        # all-auth
        'django.contrib.sites',
        'allauth',
        'allauth.account',
        'allauth.socialaccount',
        'django_extensions',
        'django_filters',
        # openwisp2 modules
        'openwisp_users',
        'openwisp_controller.pki',
        'openwisp_controller.config',
        'openwisp_controller.connection',
        'openwisp_controller.geo',
        # monitoring
        'openwisp_monitoring.monitoring',
        'openwisp_monitoring.device',
        'openwisp_monitoring.check',
        'nested_admin',
        # notifications
        'openwisp_notifications',
        # openwisp2 admin theme (must be loaded here)
        'openwisp_utils.admin_theme',
        'admin_auto_filters',
        # admin
        'django.contrib.admin',
        'django.forms',
        'import_export'
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
        'OPTIONS': {
            # Specify additional options to be used while initializing
            # database connection.
            # Note: These options may differ based on the backend used.
            'udp_writes': True,
            'udp_port': 8089,
        }
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
            'task': 'openwisp_monitoring.check.tasks.run_checks',
            # Executes only ping & config check every 5 min
            'schedule': timedelta(minutes=5),
            'args': (
                [  # Checks path
                    'openwisp_monitoring.check.classes.Ping',
                    'openwisp_monitoring.check.classes.ConfigApplied',
                ],
            ),
            'relative': True,
        },
        # Delete old WifiSession
        'delete_wifi_clients_and_sessions': {
            'task': 'openwisp_monitoring.monitoring.tasks.delete_wifi_clients_and_sessions',
            'schedule': timedelta(days=180),
        },
    }

    INSTALLED_APPS.append('djcelery_email')
    EMAIL_BACKEND = 'djcelery_email.backends.CeleryEmailBackend'

If you decide to use Redis (as shown in these examples),
install the following python packages.

.. code-block:: shell

    pip install redis django-redis

Quickstart Guide
----------------

Install OpenWISP Monitoring
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Install *OpenWISP Monitoring* using one of the methods mentioned in the
`"Installation instructions" <#installation-instructions>`_.

Install openwisp-config on the device
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`Install the openwisp-config agent for OpenWrt
<https://github.com/openwisp/openwisp-config#install-precompiled-package>`_
on your device.

Install monitoring packages on the device
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`Install the openwrt-openwisp-monitoring packages
<https://github.com/openwisp/openwrt-openwisp-monitoring/tree/master#install-pre-compiled-packages>`_
on your device.

These packages collect and send the
monitoring data from the device to OpenWISP Monitoring and
are required to collect `metrics <#openwisp_monitoring_metrics>`_
like interface traffic, WiFi clients, CPU load, memory usage, etc.

**Note**: if you are an existing user of *openwisp-monitoring* and are using
the legacy *monitoring template* for collecting metrics, we highly recommend
`Migrating from monitoring scripts to monitoring packages
<#migrating-from-monitoring-scripts-to-monitoring-packages>`_.

Make sure OpenWISP can reach your devices
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In order to perform `active checks <#available-checks>`_ and other actions like
`triggering the push of configuration changes
<https://github.com/openwisp/openwisp-controller#how-to-configure-push-updates>`_,
`executing shell commands
<https://github.com/openwisp/openwisp-controller#sending-commands-to-devices>`_ or
`performing firmware upgrades
<https://github.com/openwisp/openwisp-firmware-upgrader#perform-a-firmware-upgrade-to-a-specific-device>`_,
**the OpenWISP server needs to be able to reach the network devices**.

There are mainly two deployment scenarios for OpenWISP:

1. the OpenWISP server is deployed on the public internet and the devices are
   geographically distributed across different locations:
   **in this case a management tunnel is needed**
2. the OpenWISP server is deployed on a computer/server which is located in
   the same Layer 2 network (that is, in the same LAN) where the devices
   are located.
   **in this case a management tunnel is NOT needed**

1. Public internet deployment
#############################

This is the most common scenario:

- the OpenWISP server is deployed to the public internet, hence the
  server has a public IPv4 (and IPv6) address and usually a valid
  SSL certificate provided by Mozilla Letsencrypt or another SSL provider
- the network devices are geographically distributed across different
  locations (different cities, different regions, different countries)

In this scenario, the OpenWISP application will not be able to reach the
devices **unless a management tunnel** is used, for that reason having
a management VPN like OpenVPN, Wireguard or any other tunneling solution
is paramount, not only to allow OpenWISP to work properly, but also to
be able to perform debugging and troubleshooting when needed.

In this scenario, the following requirements are needed:

- a VPN server must be installed in a way that the OpenWISP
  server can reach the VPN peers, for more information on how to do this
  via OpenWISP please refer to the following sections:

  - `OpenVPN tunnel automation
    <https://openwisp.io/docs/user/vpn.html>`_
  - `Wireguard tunnel automation
    <https://github.com/openwisp/openwisp-controller#how-to-setup-wireguard-tunnels>`_

  If you prefer to use other tunneling solutions (L2TP, Softether, etc.)
  and know how to configure those solutions on your own,
  that's totally fine as well.

  If the OpenWISP server is connected to a network infrastructure
  which allows it to reach the devices via pre-existing tunneling or
  Intranet solutions (eg: MPLS, SD-WAN), then setting up a VPN server
  is not needed, as long as there's a dedicated interface on OpenWrt
  which gets an IP address assigned to it and which is reachable from
  the OpenWISP server.

- The devices must be configured to join the management tunnel automatically,
  either via a pre-existing configuration in the firmware or via an
  `OpenWISP Template <https://openwisp.io/docs/user/templates.html>`_.

- The `openwisp-config <https://github.com/openwisp/openwisp-config>`_
  agent on the devices must be configured to specify
  the ``management_interface`` option, the agent will communicate the
  IP of the management interface to the OpenWISP Server and OpenWISP will
  use the management IP for reaching the device.

  For example, if the *management interface* is named ``tun0``,
  the openwisp-config configuration should look like the following example:

.. code-block:: text

    # In /etc/config/openwisp on the device

    config controller 'http'
        # ... other configuration directives ...
        option management_interface 'tun0'

2. LAN deployment
#################

When the OpenWISP server and the network devices are deployed in the same
L2 network (eg: an office LAN) and the OpenWISP server is reachable
on the LAN address, OpenWISP can then use the **Last IP** field of the
devices to reach them.

In this scenario it's necessary to set the
`"OPENWISP_MONITORING_MANAGEMENT_IP_ONLY" <#openwisp-monitoring-management-ip-only>`_
setting to ``False``.

Creating checks for a device
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

By default, the `active checks <#available-checks>`_ are created
automatically for all devices, unless the automatic creation of some
specific checks has been disabled, for more information on how to do this,
refer to the `active checks <#available-checks>`_ section.

These checks are created and executed in the background by celery workers.

Passive vs Active Metric Collection
-----------------------------------

The `the different device metric
<https://github.com/openwisp/openwisp-monitoring#default-metrics>`_
collected by OpenWISP Monitoring can be divided in two categories:

1. **metrics collected actively by OpenWISP**:
   these metrics are collected by the celery workers running on the
   OpenWISP server, which continuously sends network requests to the
   devices and store the results;
2. **metrics collected passively by OpenWISP**:
   these metrics are sent by the
   `openwrt-openwisp-monitoring agent <#install-monitoring-packages-on-the-device>`_
   installed on the network devices and are collected by OpenWISP via
   its REST API.

The `"Available Checks" <#available-checks>`_ section of this document
lists the currently implemented **active checks**.

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

Default Metrics
---------------

Device Status
~~~~~~~~~~~~~

This metric stores the status of the device for viewing purposes.

.. figure:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/device-status-1.png
  :align: center

.. figure:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/device-status-2.png
  :align: center

.. figure:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/device-status-3.png
  :align: center

.. figure:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/device-status-4.png
  :align: center

Ping
~~~~

+--------------------+----------------------------------------------------------------+
| **measurement**:   | ``ping``                                                       |
+--------------------+----------------------------------------------------------------+
| **types**:         | ``int`` (reachable and loss), ``float`` (rtt)                  |
+--------------------+----------------------------------------------------------------+
| **fields**:        | ``reachable``, ``loss``, ``rtt_min``, ``rtt_max``, ``rtt_avg`` |
+--------------------+----------------------------------------------------------------+
| **configuration**: | ``ping``                                                       |
+--------------------+----------------------------------------------------------------+
| **charts**:        | ``uptime`` (Ping Success Rate), ``packet_loss``, ``rtt``       |
+--------------------+----------------------------------------------------------------+

**Ping Success Rate**:

.. figure:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/1.1/ping-success-rate.png
  :align: center

**Packet loss**:

.. figure:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/packet-loss.png
  :align: center

**Round Trip Time**:

.. figure:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/rtt.png
  :align: center

Traffic
~~~~~~~

+--------------------+--------------------------------------------------------------------------+
| **measurement**:   | ``traffic``                                                              |
+--------------------+--------------------------------------------------------------------------+
| **type**:          | ``int``                                                                  |
+--------------------+--------------------------------------------------------------------------+
| **fields**:        | ``rx_bytes``, ``tx_bytes``                                               |
+--------------------+--------------------------------------------------------------------------+
| **tags**:          | .. code-block:: python                                                   |
|                    |                                                                          |
|                    |     {                                                                    |
|                    |       'organization_id': '<organization-id-of-the-related-device>',      |
|                    |       'ifname': '<interface-name>',                                      |
|                    |       # optional                                                         |
|                    |       'location_id': '<location-id-of-the-related-device-if-present>',   |
|                    |       'floorplan_id': '<floorplan-id-of-the-related-device-if-present>', |
|                    |     }                                                                    |
+--------------------+--------------------------------------------------------------------------+
| **configuration**: | ``traffic``                                                              |
+--------------------+--------------------------------------------------------------------------+
| **charts**:        | ``traffic``                                                              |
+--------------------+--------------------------------------------------------------------------+

.. figure:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/1.1/traffic.png
  :align: center

WiFi Clients
~~~~~~~~~~~~

+--------------------+--------------------------------------------------------------------------+
| **measurement**:   | ``wifi_clients``                                                         |
+--------------------+--------------------------------------------------------------------------+
| **type**:          | ``int``                                                                  |
+--------------------+--------------------------------------------------------------------------+
| **fields**:        | ``clients``                                                              |
+--------------------+--------------------------------------------------------------------------+
| **tags**:          | .. code-block:: python                                                   |
|                    |                                                                          |
|                    |     {                                                                    |
|                    |       'organization_id': '<organization-id-of-the-related-device>',      |
|                    |       'ifname': '<interface-name>',                                      |
|                    |       # optional                                                         |
|                    |       'location_id': '<location-id-of-the-related-device-if-present>',   |
|                    |       'floorplan_id': '<floorplan-id-of-the-related-device-if-present>', |
|                    |     }                                                                    |
+--------------------+--------------------------------------------------------------------------+
| **configuration**: | ``clients``                                                              |
+--------------------+--------------------------------------------------------------------------+
| **charts**:        | ``wifi_clients``                                                         |
+--------------------+--------------------------------------------------------------------------+


.. figure:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/wifi-clients.png
  :align: center

Memory Usage
~~~~~~~~~~~~

+--------------------+--------------------------------------------------------------------------------------------------------------------------------------+
| **measurement**:   | ``<memory>``                                                                                                                         |
+--------------------+--------------------------------------------------------------------------------------------------------------------------------------+
| **type**:          | ``float``                                                                                                                            |
+--------------------+--------------------------------------------------------------------------------------------------------------------------------------+
| **fields**:        | ``percent_used``, ``free_memory``, ``total_memory``, ``buffered_memory``, ``shared_memory``, ``cached_memory``, ``available_memory`` |
+--------------------+--------------------------------------------------------------------------------------------------------------------------------------+
| **configuration**: | ``memory``                                                                                                                           |
+--------------------+--------------------------------------------------------------------------------------------------------------------------------------+
| **charts**:        | ``memory``                                                                                                                           |
+--------------------+--------------------------------------------------------------------------------------------------------------------------------------+

.. figure:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/memory.png
  :align: center

CPU Load
~~~~~~~~

+--------------------+----------------------------------------------------+
| **measurement**:   | ``load``                                           |
+--------------------+----------------------------------------------------+
| **type**:          | ``float``                                          |
+--------------------+----------------------------------------------------+
| **fields**:        | ``cpu_usage``, ``load_1``, ``load_5``, ``load_15`` |
+--------------------+----------------------------------------------------+
| **configuration**: | ``load``                                           |
+--------------------+----------------------------------------------------+
| **charts**:        | ``load``                                           |
+--------------------+----------------------------------------------------+

.. figure:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/cpu-load.png
  :align: center

Disk Usage
~~~~~~~~~~

+--------------------+-------------------+
| **measurement**:   | ``disk``          |
+--------------------+-------------------+
| **type**:          | ``float``         |
+--------------------+-------------------+
| **fields**:        | ``used_disk``     |
+--------------------+-------------------+
| **configuration**: | ``disk``          |
+--------------------+-------------------+
| **charts**:        | ``disk``          |
+--------------------+-------------------+

.. figure:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/disk-usage.png
  :align: center

Mobile Signal Strength
~~~~~~~~~~~~~~~~~~~~~~

+--------------------+-----------------------------------------+
| **measurement**:   | ``signal_strength``                     |
+--------------------+-----------------------------------------+
| **type**:          | ``float``                               |
+--------------------+-----------------------------------------+
| **fields**:        | ``signal_strength``, ``signal_power``   |
+--------------------+-----------------------------------------+
| **configuration**: | ``signal_strength``                     |
+--------------------+-----------------------------------------+
| **charts**:        | ``signal_strength``                     |
+--------------------+-----------------------------------------+

.. figure:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/signal-strength.png
  :align: center

Mobile Signal Quality
~~~~~~~~~~~~~~~~~~~~~~

+--------------------+-----------------------------------------+
| **measurement**:   | ``signal_quality``                      |
+--------------------+-----------------------------------------+
| **type**:          | ``float``                               |
+--------------------+-----------------------------------------+
| **fields**:        | ``signal_quality``, ``signal_quality``  |
+--------------------+-----------------------------------------+
| **configuration**: | ``signal_quality``                      |
+--------------------+-----------------------------------------+
| **charts**:        | ``signal_quality``                      |
+--------------------+-----------------------------------------+

.. figure:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/signal-quality.png
  :align: center

Mobile Access Technology in use
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+--------------------+-------------------+
| **measurement**:   | ``access_tech``   |
+--------------------+-------------------+
| **type**:          | ``int``           |
+--------------------+-------------------+
| **fields**:        | ``access_tech``   |
+--------------------+-------------------+
| **configuration**: | ``access_tech``   |
+--------------------+-------------------+
| **charts**:        | ``access_tech``   |
+--------------------+-------------------+

.. figure:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/access-technology.png
  :align: center

Iperf3
~~~~~~

+--------------------+---------------------------------------------------------------------------------------------------------------------------+
| **measurement**:   | ``iperf3``                                                                                                                |
+--------------------+---------------------------------------------------------------------------------------------------------------------------+
| **types**:         | | ``int`` (iperf3_result, sent_bytes_tcp, received_bytes_tcp, retransmits, sent_bytes_udp, total_packets, lost_packets),  |
|                    | | ``float`` (sent_bps_tcp, received_bps_tcp, sent_bps_udp, jitter, lost_percent)                                          |
+--------------------+---------------------------------------------------------------------------------------------------------------------------+
| **fields**:        | | ``iperf3_result``, ``sent_bps_tcp``, ``received_bps_tcp``, ``sent_bytes_tcp``, ``received_bytes_tcp``, ``retransmits``, |
|                    | | ``sent_bps_udp``, ``sent_bytes_udp``, ``jitter``, ``total_packets``, ``lost_packets``, ``lost_percent``                 |
+--------------------+---------------------------------------------------------------------------------------------------------------------------+
| **configuration**: | ``iperf3``                                                                                                                |
+--------------------+---------------------------------------------------------------------------------------------------------------------------+
| **charts**:        | ``bandwidth``, ``transfer``, ``retransmits``, ``jitter``, ``datagram``, ``datagram_loss``                                 |
+--------------------+---------------------------------------------------------------------------------------------------------------------------+

**Bandwidth**:

.. figure:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/1.1/bandwidth.png
  :align: center

**Transferred Data**:

.. figure:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/1.1/transferred-data.png
  :align: center

**Retransmits**:

.. figure:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/1.1/retransmits.png
  :align: center

**Jitter**:

.. figure:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/1.1/jitter.png
  :align: center

**Datagram**:

.. figure:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/1.1/datagram.png
  :align: center

**Datagram loss**:

.. figure:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/1.1/datagram-loss.png
  :align: center

For more info on how to configure and use Iperf3, please refer to
`iperf3 check usage instructions <#iperf3-check-usage-instructions>`_.

**Note:** Iperf3 charts uses ``connect_points=True`` in
`default chart configuration <#openwisp_monitoring_charts>`_ that joins it's individual chart data points.

Dashboard Monitoring Charts
---------------------------

.. figure:: https://github.com/openwisp/openwisp-monitoring/blob/docs/docs/1.1/dashboard-charts.png
  :align: center

OpenWISP Monitoring adds two timeseries charts to the admin dashboard:

- **General WiFi clients Chart**: Shows the number of connected clients to the WiFi
  interfaces of devices in the network.
- **General traffic Chart**: Shows the amount of traffic flowing in the network.

You can configure the interfaces included in the **General traffic chart** using
the `"OPENWISP_MONITORING_DASHBOARD_TRAFFIC_CHART"
<#openwisp_monitoring_dashboard_traffic_chart>`_ setting.

Adaptive size charts
--------------------

.. figure:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/1.1/adaptive-chart.png
   :align: center

When configuring charts, it is possible to flag their unit
as ``adaptive_prefix``, this allows to make the charts more readable because
the units are shown in either `K`, `M`, `G` and `T` depending on
the size of each point, the summary values and Y axis are also resized.

Example taken from the default configuration of the traffic chart:

.. code-block:: python

    'traffic': {
        # other configurations for this chart

        # traffic measured in 'B' (bytes)
        # unit B, KB, MB, GB, TB
        'unit': 'adaptive_prefix+B',
    },

    'bandwidth': {
        # adaptive unit for bandwidth related charts
        # bandwidth measured in 'bps'(bits/sec)
        # unit bps, Kbps, Mbps, Gbps, Tbps
        'unit': 'adaptive_prefix+bps',
    },

Monitoring WiFi Sessions
------------------------

OpenWISP Monitoring maintains a record of WiFi sessions created by clients
joined to a radio of managed devices. The WiFi sessions are created
asynchronously from the monitoring data received from the device.

You can filter both currently open sessions and past sessions by their
*start* or *stop* time or *organization* or *group* of the device clients
are connected to or even directly by a *device* name or ID.

.. figure:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/wifi-session-changelist.png
  :align: center

.. figure:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/wifi-session-change.png
  :align: center

You can disable this feature by configuring
`OPENWISP_MONITORING_WIFI_SESSIONS_ENABLED <#openwisp_monitoring_wifi_sessions_enabled>`_
setting.

You can also view open WiFi sessions of a device directly from the device's change admin
under the "WiFi Sessions" tab.

.. figure:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/device-wifi-session-inline.png
  :align: center

Scheduled deletion of WiFi sessions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

OpenWISP Monitoring provides a celery task to automatically delete
WiFi sessions older than a pre-configured number of days. In order to run this
task periodically, you will need to configure ``CELERY_BEAT_SCHEDULE`` setting as shown
in `setup instructions <#setup-integrate-in-an-existing-django-project>`_.

The celery task takes only one argument, i.e. number of days. You can provide
any number of days in `args` key while configuring ``CELERY_BEAT_SCHEDULE`` setting.

E.g., if you want WiFi Sessions older than 30 days to get deleted automatically,
then configure ``CELERY_BEAT_SCHEDULE`` as follows:

.. code-block:: python

    CELERY_BEAT_SCHEDULE = {
        'delete_wifi_clients_and_sessions': {
            'task': 'openwisp_monitoring.monitoring.tasks.delete_wifi_clients_and_sessions',
            'schedule': timedelta(days=1),
            'args': (30,), # Here we have defined 30 instead of 180 as shown in setup instructions
        },
    }

Please refer to `"Periodic Tasks" section of Celery's documentation <https://docs.celeryproject.org/en/stable/userguide/periodic-tasks.html>`_
to learn more.

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

Available Checks
----------------

Ping
~~~~

This check returns information on Ping Success Rate and RTT (Round trip time).
It creates charts like Ping Success Rate, Packet Loss and RTT.
These metrics are collected using the ``fping`` Linux program.
You may choose to disable auto creation of this check by setting
`OPENWISP_MONITORING_AUTO_PING <#OPENWISP_MONITORING_AUTO_PING>`_ to ``False``.

You can change the default values used for ping checks using
`OPENWISP_MONITORING_PING_CHECK_CONFIG <#OPENWISP_MONITORING_PING_CHECK_CONFIG>`_ setting.

Configuration applied
~~~~~~~~~~~~~~~~~~~~~

This check ensures that the `openwisp-config agent <https://github.com/openwisp/openwisp-config/>`_
is running and applying configuration changes in a timely manner.
You may choose to disable auto creation of this check by using the
setting `OPENWISP_MONITORING_AUTO_DEVICE_CONFIG_CHECK <#OPENWISP_MONITORING_AUTO_DEVICE_CONFIG_CHECK>`_.

This check runs periodically, but it is also triggered whenever the
configuration status of a device changes, this ensures the check reacts
quickly to events happening in the network and informs the user promptly
if there's anything that is not working as intended.

Iperf3
~~~~~~

This check provides network performance measurements such as maximum achievable bandwidth,
jitter, datagram loss etc of the device using `iperf3 utility <https://iperf.fr/>`_.

This check is **disabled by default**. You can enable auto creation of this check by setting the
`OPENWISP_MONITORING_AUTO_IPERF3 <#OPENWISP_MONITORING_AUTO_IPERF3>`_ to ``True``.

You can also `add the iperf3 check
<#add-checks-and-alert-settings-from-the-device-page>`_ directly from the device page.

It also supports tuning of various parameters.

You can also change the parameters used for iperf3 checks (e.g. timing, port, username,
password, rsa_publc_key etc) using the `OPENWISP_MONITORING_IPERF3_CHECK_CONFIG
<#OPENWISP_MONITORING_IPERF3_CHECK_CONFIG>`_ setting.

**Note:** When setting `OPENWISP_MONITORING_AUTO_IPERF3 <#OPENWISP_MONITORING_AUTO_IPERF3>`_  to ``True``,
you may need to update the `metric configuration <#add-checks-and-alert-settings-from-the-device-page>`_
to enable alerts for the iperf3 check.

Iperf3 Check Usage Instructions
-------------------------------

1. Make sure iperf3 is installed on the device
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Register your device to OpenWISP and make sure the `iperf3 openwrt package
<https://openwrt.org/packages/pkgdata/iperf3>`_ is installed on the device,
eg:

.. code-block:: shell

    opkg install iperf3  # if using without authentication
    opkg install iperf3-ssl  # if using with authentication (read below for more info)

2. Ensure SSH access from OpenWISP is enabled on your devices
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Follow the steps in `"How to configure push updates" section of the
OpenWISP documentation
<https://openwisp.io/docs/user/configure-push-updates.html>`_
to allow SSH access to you device from OpenWISP.

**Note:** Make sure device connection is enabled
& working with right update strategy i.e. ``OpenWRT SSH``.

.. image:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/1.1/enable-openwrt-ssh.png
  :alt: Enable ssh access from openwisp to device
  :align: center

3. Set up and configure Iperf3 server settings
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

After having deployed your Iperf3 servers, you need to
configure the iperf3 settings on the django side of OpenWISP,
see the `test project settings for reference
<https://github.com/openwisp/openwisp-monitoring/blob/master/tests/openwisp2/settings.py>`_.

The host can be specified by hostname, IPv4 literal, or IPv6 literal.
Example:

.. code-block:: python

   OPENWISP_MONITORING_IPERF3_CHECK_CONFIG = {
       # 'org_pk' : {'host' : [], 'client_options' : {}}
       'a9734710-db30-46b0-a2fc-01f01046fe4f': {
           # Some public iperf3 servers
           # https://iperf.fr/iperf-servers.php#public-servers
           'host': ['iperf3.openwisp.io', '2001:db8::1', '192.168.5.2'],
           'client_options': {
               'port': 5209,
               'udp': {'bitrate': '30M'},
               'tcp': {'bitrate': '0'},
           },
       },
       # another org
       'b9734710-db30-46b0-a2fc-01f01046fe4f': {
           # available iperf3 servers
           'host': ['iperf3.openwisp2.io', '192.168.5.3'],
           'client_options': {
               'port': 5207,
               'udp': {'bitrate': '50M'},
               'tcp': {'bitrate': '20M'},
           },
       },
   }

**Note:** If an organization has more than one iperf3 server configured, then it enables
the iperf3 checks to run concurrently on different devices. If all of the available servers
are busy, then it will add the check back in the queue.

The celery-beat configuration for the iperf3 check needs to be added too:

.. code-block:: python

    from celery.schedules import crontab

    # Celery TIME_ZONE should be equal to django TIME_ZONE
    # In order to schedule run_iperf3_checks on the correct time intervals
    CELERY_TIMEZONE = TIME_ZONE
    CELERY_BEAT_SCHEDULE = {
        # Other celery beat configurations
        # Celery beat configuration for iperf3 check
        'run_iperf3_checks': {
            'task': 'openwisp_monitoring.check.tasks.run_checks',
            # https://docs.celeryq.dev/en/latest/userguide/periodic-tasks.html#crontab-schedules
            # Executes check every 5 mins from 00:00 AM to 6:00 AM (night)
            'schedule': crontab(minute='*/5', hour='0-6'),
            # Iperf3 check path
            'args': (['openwisp_monitoring.check.classes.Iperf3'],),
            'relative': True,
        }
    }

Once the changes are saved, you will need to restart all the processes.

**Note:** We recommended to configure this check to run in non peak
traffic times to not interfere with standard traffic.

4. Run the check
~~~~~~~~~~~~~~~~

This should happen automatically if you have celery-beat correctly
configured and running in the background.
For testing purposes, you can run this check manually using the
`run_checks <#run_checks>`_ command.

After that, you should see the iperf3 network measurements charts.

.. image:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/1.1/iperf3-charts.png
  :alt: Iperf3 network measurement charts

Iperf3 check parameters
~~~~~~~~~~~~~~~~~~~~~~~

Currently, iperf3 check supports the following parameters:

+-----------------------+----------+--------------------------------------------------------------------+
| **Parameter**         | **Type** | **Default Value**                                                  |
+-----------------------+----------+--------------------------------------------------------------------+
|``host``               | ``list`` | ``[]``                                                             |
+-----------------------+----------+--------------------------------------------------------------------+
|``username``           | ``str``  | ``''``                                                             |
+-----------------------+----------+--------------------------------------------------------------------+
|``password``           | ``str``  | ``''``                                                             |
+-----------------------+----------+--------------------------------------------------------------------+
|``rsa_public_key``     | ``str``  | ``''``                                                             |
+-----------------------+----------+--------------------------------------------------------------------+
|``client_options``     | +---------------------+----------+------------------------------------------+ |
|                       | | **Parameters**      | **Type** | **Default Value**                        | |
|                       | +---------------------+----------+------------------------------------------+ |
|                       | | ``port``            | ``int``  | ``5201``                                 | |
|                       | +---------------------+----------+------------------------------------------+ |
|                       | | ``time``            | ``int``  | ``10``                                   | |
|                       | +---------------------+----------+------------------------------------------+ |
|                       | | ``bytes``           | ``str``  | ``''``                                   | |
|                       | +---------------------+----------+------------------------------------------+ |
|                       | | ``blockcount``      | ``str``  | ``''``                                   | |
|                       | +---------------------+----------+------------------------------------------+ |
|                       | | ``window``          | ``str``  | ``0``                                    | |
|                       | +---------------------+----------+------------------------------------------+ |
|                       | | ``parallel``        | ``int``  | ``1``                                    | |
|                       | +---------------------+----------+------------------------------------------+ |
|                       | | ``reverse``         | ``bool`` | ``False``                                | |
|                       | +---------------------+----------+------------------------------------------+ |
|                       | | ``bidirectional``   | ``bool`` | ``False``                                | |
|                       | +---------------------+----------+------------------------------------------+ |
|                       | | ``connect_timeout`` | ``int``  | ``1000``                                 | |
|                       | +---------------------+----------+------------------------------------------+ |
|                       | | ``tcp``             | +----------------+----------+---------------------+ | |
|                       | |                     | | **Parameters** | **Type** | **Default Value**   | | |
|                       | |                     | +----------------+----------+---------------------+ | |
|                       | |                     | |``bitrate``     | ``str``  | ``0``               | | |
|                       | |                     | +----------------+----------+---------------------+ | |
|                       | |                     | |``length``      | ``str``  | ``128K``            | | |
|                       | |                     | +----------------+----------+---------------------+ | |
|                       | +---------------------+-----------------------------------------------------+ |
|                       | | ``udp``             | +----------------+----------+---------------------+ | |
|                       | |                     | | **Parameters** | **Type** | **Default Value**   | | |
|                       | |                     | +----------------+----------+---------------------+ | |
|                       | |                     | |``bitrate``     | ``str``  | ``30M``             | | |
|                       | |                     | +----------------+----------+---------------------+ | |
|                       | |                     | |``length``      | ``str``  | ``0``               | | |
|                       | |                     | +----------------+----------+---------------------+ | |
|                       | +---------------------+-----------------------------------------------------+ |
+-----------------------+-------------------------------------------------------------------------------+

To learn how to use these parameters, please see the
`iperf3 check configuration example <#OPENWISP_MONITORING_IPERF3_CHECK_CONFIG>`_.

Visit the `official documentation <https://www.mankier.com/1/iperf3>`_
to learn more about the iperf3 parameters.

Iperf3 authentication
~~~~~~~~~~~~~~~~~~~~~

By default iperf3 check runs without any kind of **authentication**,
in this section we will explain how to configure **RSA authentication**
between the **client** and the **server** to restrict connections
to authenticated clients.

Server side
###########

1. Generate RSA keypair
^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: shell

   openssl genrsa -des3 -out private.pem 2048
   openssl rsa -in private.pem -outform PEM -pubout -out public_key.pem
   openssl rsa -in private.pem -out private_key.pem -outform PEM

After running the commands mentioned above, the public key will be stored in
``public_key.pem`` which will be used in **rsa_public_key** parameter
in `OPENWISP_MONITORING_IPERF3_CHECK_CONFIG
<#OPENWISP_MONITORING_IPERF3_CHECK_CONFIG>`_
and the private key will be contained in the file ``private_key.pem``
which will be used with **--rsa-private-key-path** command option when
starting the iperf3 server.

2. Create user credentials
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: shell

   USER=iperfuser PASSWD=iperfpass
   echo -n "{$USER}$PASSWD" | sha256sum | awk '{ print $1 }'
   ----
   ee17a7f98cc87a6424fb52682396b2b6c058e9ab70e946188faa0714905771d7 #This is the hash of "iperfuser"

Add the above hash with username in ``credentials.csv``

.. code-block:: shell

   # file format: username,sha256
   iperfuser,ee17a7f98cc87a6424fb52682396b2b6c058e9ab70e946188faa0714905771d7

3. Now start the iperf3 server with auth options
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: shell

   iperf3 -s --rsa-private-key-path ./private_key.pem --authorized-users-path ./credentials.csv

Client side (OpenWrt device)
############################

1. Install iperf3-ssl
^^^^^^^^^^^^^^^^^^^^^

Install the `iperf3-ssl openwrt package
<https://openwrt.org/packages/pkgdata/iperf3-ssl>`_
instead of the normal
`iperf3 openwrt package <https://openwrt.org/packages/pkgdata/iperf3>`_
because the latter comes without support for authentication.

You may also check your installed **iperf3 openwrt package** features:

.. code-block:: shell

   root@vm-openwrt:~ iperf3 -v
   iperf 3.7 (cJSON 1.5.2)
   Linux vm-openwrt 4.14.171 #0 SMP Thu Feb 27 21:05:12 2020 x86_64
   Optional features available: CPU affinity setting, IPv6 flow label, TCP congestion algorithm setting,
   sendfile / zerocopy, socket pacing, authentication # contains 'authentication'

2. Configure iperf3 check auth parameters
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Now, add the following iperf3 authentication parameters
to `OPENWISP_MONITORING_IPERF3_CHECK_CONFIG
<#OPENWISP_MONITORING_IPERF3_CHECK_CONFIG>`_
in the settings:

.. code-block:: python

   OPENWISP_MONITORING_IPERF3_CHECK_CONFIG = {
       'a9734710-db30-46b0-a2fc-01f01046fe4f': {
           'host': ['iperf1.openwisp.io', 'iperf2.openwisp.io', '192.168.5.2'],
           # All three parameters (username, password, rsa_publc_key)
           # are required for iperf3 authentication
           'username': 'iperfuser',
           'password': 'iperfpass',
           # Add RSA public key without any headers
           # ie. -----BEGIN PUBLIC KEY-----, -----BEGIN END KEY-----
           'rsa_public_key': (
               """
               MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAwuEm+iYrfSWJOupy6X3N
               dxZvUCxvmoL3uoGAs0O0Y32unUQrwcTIxudy38JSuCccD+k2Rf8S4WuZSiTxaoea
               6Du99YQGVZeY67uJ21SWFqWU+w6ONUj3TrNNWoICN7BXGLE2BbSBz9YaXefE3aqw
               GhEjQz364Itwm425vHn2MntSp0weWb4hUCjQUyyooRXPrFUGBOuY+VvAvMyAG4Uk
               msapnWnBSxXt7Tbb++A5XbOMdM2mwNYDEtkD5ksC/x3EVBrI9FvENsH9+u/8J9Mf
               2oPl4MnlCMY86MQypkeUn7eVWfDnseNky7TyC0/IgCXve/iaydCCFdkjyo1MTAA4
               BQIDAQAB
               """
           ),
           'client_options': {
               'port': 5209,
               'udp': {'bitrate': '20M'},
               'tcp': {'bitrate': '0'},
           },
       }
   }

Adding Checks and Alert settings from the device page
-----------------------------------------------------

We can add checks and define alert settings directly from the **device page**.

To add a check, you just need to select an available **check type** as shown below:

.. figure:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/1.1/device-inline-check.png
  :align: center

The following example shows how to use the
`OPENWISP_MONITORING_METRICS setting <#openwisp_monitoring_metrics>`_
to reconfigure the system for `iperf3 check <#iperf3-1>`_ to send an alert if
the measured **TCP bandwidth** has been less than **10 Mbit/s** for more than **2 days**.

1. By default, `Iperf3 checks <#iperf3-1>`_ come with default alert settings,
but it is easy to customize alert settings through the device page as shown below:

.. figure:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/1.1/device-inline-alertsettings.png
  :align: center

2. Now, add the following notification configuration to send an alert for **TCP bandwidth**:

.. code-block:: python

   # Main project settings.py
   from django.utils.translation import gettext_lazy as _

   OPENWISP_MONITORING_METRICS = {
       'iperf3': {
           'notification': {
               'problem': {
                   'verbose_name': 'Iperf3 PROBLEM',
                   'verb': _('Iperf3 bandwidth is less than normal value'),
                   'level': 'warning',
                   'email_subject': _(
                       '[{site.name}] PROBLEM: {notification.target} {notification.verb}'
                   ),
                   'message': _(
                       'The device [{notification.target}]({notification.target_link}) '
                       '{notification.verb}.'
                   ),
               },
               'recovery': {
                   'verbose_name': 'Iperf3 RECOVERY',
                   'verb': _('Iperf3 bandwidth now back to normal'),
                   'level': 'info',
                   'email_subject': _(
                       '[{site.name}] RECOVERY: {notification.target} {notification.verb}'
                   ),
                   'message': _(
                       'The device [{notification.target}]({notification.target_link}) '
                       '{notification.verb}.'
                   ),
               },
           },
       },
   }

.. figure:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/1.1/alert_field_warn.png
  :align: center

.. figure:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/1.1/alert_field_info.png
  :align: center

**Note:** To access the features described above, the user must have permissions for ``Check`` and ``AlertSetting`` inlines,
these permissions are included by default in the "Administrator" and "Operator" groups and are shown in the screenshot below.

.. figure:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/1.1/inline-permissions.png
  :align: center

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

Registering / Unregistering Metric Configuration
------------------------------------------------

**OpenWISP Monitoring** provides registering and unregistering metric configuration through utility functions
``openwisp_monitoring.monitoring.configuration.register_metric`` and ``openwisp_monitoring.monitoring.configuration.unregister_metric``.
Using these functions you can register or unregister metric configurations from anywhere in your code.

``register_metric``
~~~~~~~~~~~~~~~~~~~

This function is used to register a new metric configuration from anywhere in your code.

+--------------------------+------------------------------------------------------+
|      **Parameter**       |                   **Description**                    |
+--------------------------+------------------------------------------------------+
|     **metric_name**:     | A ``str`` defining name of the metric configuration. |
+--------------------------+------------------------------------------------------+
|**metric_configuration**: | A ``dict`` defining configuration of the metric.     |
+--------------------------+------------------------------------------------------+

An example usage has been shown below.

.. code-block:: python

    from django.utils.translation import gettext_lazy as _
    from openwisp_monitoring.monitoring.configuration import register_metric

    # Define configuration of your metric
    metric_config = {
        'label': _('Ping'),
        'name': 'Ping',
        'key': 'ping',
        'field_name': 'reachable',
        'related_fields': ['loss', 'rtt_min', 'rtt_max', 'rtt_avg'],
        'charts': {
            'uptime': {
                'type': 'bar',
                'title': _('Ping Success Rate'),
                'description': _(
                    'A value of 100% means reachable, 0% means unreachable, values in '
                    'between 0% and 100% indicate the average reachability in the '
                    'period observed. Obtained with the fping linux program.'
                ),
                'summary_labels': [_('Average Ping Success Rate')],
                'unit': '%',
                'order': 200,
                'colorscale': {
                    'max': 100,
                    'min': 0,
                    'label': _('Rate'),
                    'scale': [
                        [[0, '#c13000'],
                        [0.1,'cb7222'],
                        [0.5,'#deed0e'],
                        [0.9, '#7db201'],
                        [1, '#498b26']],
                    ],
                    'map': [
                       [100, '#498b26', _('Flawless')],
                       [90, '#7db201', _('Mostly Reachable')],
                       [50, '#deed0e', _('Partly Reachable')],
                       [10, '#cb7222', _('Mostly Unreachable')],
                       [None, '#c13000', _('Unreachable')],
                    ],
                    'fixed_value': 100,
                },
                'query': chart_query['uptime'],
            },
            'packet_loss': {
                'type': 'bar',
                'title': _('Packet loss'),
                'description': _(
                    'Indicates the percentage of lost packets observed in ICMP probes. '
                    'Obtained with the fping linux program.'
                ),
                'summary_labels': [_('Average packet loss')],
                'unit': '%',
                'colors': '#d62728',
                'order': 210,
                'query': chart_query['packet_loss'],
            },
            'rtt': {
                'type': 'scatter',
                'title': _('Round Trip Time'),
                'description': _(
                    'Round trip time observed in ICMP probes, measuered in milliseconds.'
                ),
                'summary_labels': [
                    _('Average RTT'),
                    _('Average Max RTT'),
                    _('Average Min RTT'),
                ],
                'unit': _(' ms'),
                'order': 220,
                'query': chart_query['rtt'],
            },
        },
        'alert_settings': {'operator': '<', 'threshold': 1, 'tolerance': 0},
        'notification': {
            'problem': {
                'verbose_name': 'Ping PROBLEM',
                'verb': 'cannot be reached anymore',
                'level': 'warning',
                'email_subject': _(
                    '[{site.name}] {notification.target} is not reachable'
                ),
                'message': _(
                    'The device [{notification.target}] {notification.verb} anymore by our ping '
                    'messages.'
                ),
            },
            'recovery': {
                'verbose_name': 'Ping RECOVERY',
                'verb': 'has become reachable',
                'level': 'info',
                'email_subject': _(
                    '[{site.name}] {notification.target} is reachable again'
                ),
                'message': _(
                    'The device [{notification.target}] {notification.verb} again by our ping '
                    'messages.'
                ),
            },
        },
    }

    # Register your custom metric configuration
    register_metric('ping', metric_config)

The above example will register one metric configuration (named ``ping``), three chart
configurations (named ``rtt``, ``packet_loss``, ``uptime``) as defined in the **charts** key,
two notification types (named ``ping_recovery``, ``ping_problem``) as defined in **notification** key.

The ``AlertSettings`` of ``ping`` metric will by default use ``threshold`` and ``tolerance``
defined in the ``alert_settings`` key.
You can always override them and define your own custom values via the *admin*.

You can also use the ``alert_field`` key in metric configuration
which allows ``AlertSettings`` to check the ``threshold`` on
``alert_field`` instead of the default ``field_name`` key.

**Note**: It will raise ``ImproperlyConfigured`` exception if a metric configuration
is already registered with same name (not to be confused with verbose_name).

If you don't need to register a new metric but need to change a specific key of an
existing metric configuration, you can use `OPENWISP_MONITORING_METRICS <#openwisp_monitoring_metrics>`_.

``unregister_metric``
~~~~~~~~~~~~~~~~~~~~~

This function is used to unregister a metric configuration from anywhere in your code.

+------------------+------------------------------------------------------+
|  **Parameter**   |                   **Description**                    |
+------------------+------------------------------------------------------+
| **metric_name**: | A ``str`` defining name of the metric configuration. |
+------------------+------------------------------------------------------+

An example usage is shown below.

.. code-block:: python

    from openwisp_monitoring.monitoring.configuration import unregister_metric

    # Unregister previously registered metric configuration
    unregister_metric('metric_name')

**Note**: It will raise ``ImproperlyConfigured`` exception if the concerned metric
configuration is not registered.

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
existing chart configuration, you can use `OPENWISP_MONITORING_CHARTS <#openwisp_monitoring_charts>`_.

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

Registering new notification types
----------------------------------

You can define your own notification types using ``register_notification_type`` function from OpenWISP
Notifications. For more information, see the relevant `openwisp-notifications section about registering notification types
<https://github.com/openwisp/openwisp-notifications#registering--unregistering-notification-types>`_.

Once a new notification type is registered, you have to use the `"notify" signal provided in
openwisp-notifications <https://github.com/openwisp/openwisp-notifications#sending-notifications>`_
to send notifications for this type.

Exceptions
----------

``TimeseriesWriteException``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Path**: ``openwisp_monitoring.db.exceptions.TimeseriesWriteException``

If there is any failure due while writing data in timeseries database, this exception shall
be raised with a helpful error message explaining the cause of the failure.
This exception will normally be caught and the failed write task will be retried in the background
so that there is no loss of data if failures occur due to overload of Timeseries server.
You can read more about this retry mechanism at `OPENWISP_MONITORING_WRITE_RETRY_OPTIONS <#openwisp-monitoring-write-retry-options>`_.

``InvalidMetricConfigException``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Path**: ``openwisp_monitoring.monitoring.exceptions.InvalidMetricConfigException``

This exception shall be raised if the metric configuration is broken.

``InvalidChartConfigException``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Path**: ``openwisp_monitoring.monitoring.exceptions.InvalidChartConfigException``

This exception shall be raised if the chart configuration is broken.

Rest API
--------

Live documentation
~~~~~~~~~~~~~~~~~~

.. image:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/api-doc.png

A general live API documentation (following the OpenAPI specification) at ``/api/v1/docs/``.

Browsable web interface
~~~~~~~~~~~~~~~~~~~~~~~

.. image:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/api-ui-1.png
.. image:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/api-ui-2.png

Additionally, opening any of the endpoints `listed below <#list-of-endpoints>`_
directly in the browser will show the `browsable API interface of Django-REST-Framework
<https://www.django-rest-framework.org/topics/browsable-api/>`_,
which makes it even easier to find out the details of each endpoint.

List of endpoints
~~~~~~~~~~~~~~~~~

Since the detailed explanation is contained in the `Live documentation <#live-documentation>`_
and in the `Browsable web page <#browsable-web-interface>`_ of each point,
here we'll provide just a list of the available endpoints,
for further information please open the URL of the endpoint in your browser.

Retrieve general monitoring charts
##################################

.. code-block:: text

    GET /api/v1/monitoring/dashboard/

This API endpoint is used to show dashboard monitoring charts. It supports
multi-tenancy and allows filtering monitoring data by ``organization_slug``,
``location_id`` and ``floorplan_id`` e.g.:

.. code-block:: text

    GET /api/v1/monitoring/dashboard/?organization_slug=<org1-slug>,<org2-slug>&location_id=<location1-id>,<location2-id>&floorplan_id=<floorplan1-id>,<floorplan2-id>

- When retrieving chart data, the ``time`` parameter allows to specify
  the time frame, eg:

  - ``1d``: returns data of the last day
  - ``3d``: returns data of the last 3 days
  - ``7d``: returns data of the last 7 days
  - ``30d``: returns data of the last 30 days
  - ``365d``: returns data of the last 365 days

- In alternative to ``time`` it is possible to request chart data for a custom
  date range by using the ``start`` and ``end`` parameters, eg:

.. code-block:: text

    GET /api/v1/monitoring/dashboard/?start={start_datetime}&end={end_datetime}

**Note**: ``start`` and  ``end`` parameters should be in the format
``YYYY-MM-DD H:M:S``, otherwise 400 Bad Response will be returned.

Retrieve device charts and device status data
#############################################

.. code-block:: text

    GET /api/v1/monitoring/device/{pk}/?key={key}&status=true&time={timeframe}

The format used for Device Status is inspired by
`NetJSON DeviceMonitoring <http://netjson.org/docs/what.html#devicemonitoring>`_.

**Notes**:

- If the request is made without ``?status=true`` the response will
  contain only charts data and will not include any device status information
  (current load average, ARP table, DCHP leases, etc.).

- When retrieving chart data, the ``time`` parameter allows to specify
  the time frame, eg:

  - ``1d``: returns data of the last day
  - ``3d``: returns data of the last 3 days
  - ``7d``: returns data of the last 7 days
  - ``30d``: returns data of the last 30 days
  - ``365d``: returns data of the last 365 days

- In alternative to ``time`` it is possible to request chart data for a custom
  date range by using the ``start`` and ``end`` parameters, eg:

- The response contains device information, monitoring status (health status),
  a list of metrics with their respective statuses, chart data and
  device status information (only if ``?status=true``).

- This endpoint can be accessed with session authentication, token authentication,
  or alternatively with the device key passed as query string parameter
  as shown below (`?key={key}`);
  note: this method is meant to be used by the devices.

.. code-block:: text

    GET /api/v1/monitoring/device/{pk}/?key={key}&status=true&start={start_datetime}&end={end_datetime}

**Note**: ``start`` and  ``end`` parameters must be in the format
``YYYY-MM-DD H:M:S``, otherwise 400 Bad Response will be returned.

List device monitoring information
##################################

.. code-block:: text

    GET /api/v1/monitoring/device/

**Notes**:

- The response contains device information and monitoring status (health status),
  but it does not include the information and
  health status of the specific metrics, this information
  can be retrieved in the detail endpoint of each device.

- This endpoint can be accessed with session authentication and token authentication.

**Available filters**

Data can be filtered by health status (e.g. critical, ok, problem, and unknown)
to obtain the list of devices in the corresponding status, for example,
to retrieve the list of devices which are in critical conditions
(eg: unreachable), the following will work:

.. code-block:: text

   GET /api/v1/monitoring/device/?monitoring__status=critical

To filter a list of device monitoring data based
on their organization, you can use the ``organization_id``.

.. code-block:: text

   GET /api/v1/monitoring/device/?organization={organization_id}

To filter a list of device monitoring data based
on their organization slug, you can use the ``organization_slug``.

.. code-block:: text

   GET /api/v1/monitoring/device/?organization_slug={organization_slug}

Collect device metrics and status
#################################

.. code-block:: text

    POST /api/v1/monitoring/device/{pk}/?key={key}&time={datetime}

If data is latest then an additional parameter current can also be passed. For e.g.:

.. code-block:: text

    POST /api/v1/monitoring/device/{pk}/?key={key}&time={datetime}&current=true

The format used for Device Status is inspired by
`NetJSON DeviceMonitoring <http://netjson.org/docs/what.html#devicemonitoring>`_.

**Note**: the device data will be saved in the timeseries database using
the date time specified ``time``, this should be in the format
``%d-%m-%Y_%H:%M:%S.%f``, otherwise 400 Bad Response will be returned.

If the request is made without passing the ``time`` argument,
the server local time will be used.

The ``time`` parameter was added to support `resilient collection
and sending of data by the OpenWISP Monitoring Agent
<https://github.com/openwisp/openwrt-openwisp-monitoring#collecting-vs-sending>`_,
this feature allows sending data collected while the device is offline.

List nearby devices
###################

.. code-block:: text

    GET /api/v1/monitoring/device/{pk}/nearby-devices/

Returns list of nearby devices along with respective distance (in metres) and
monitoring status.

**Available filters**

The list of nearby devices provides the following filters:

- ``organization`` (Organization ID of the device)
- ``organization__slug``  (Organization slug of the device)
- ``monitoring__status``  (Monitoring status (``unknown``, ``ok``, ``problem``, or ``critical``))
- ``model`` (Pipe `|` separated list of device models)
- ``distance__lte`` (Distance in metres)

Here's a few examples:

.. code-block:: text

   GET /api/v1/monitoring/device/{pk}/nearby-devices/?organization={organization_id}
   GET /api/v1/monitoring/device/{pk}/nearby-devices/?organization__slug={organization_slug}
   GET /api/v1/monitoring/device/{pk}/nearby-devices/?monitoring__status={monitoring_status}
   GET /api/v1/monitoring/device/{pk}/nearby-devices/?model={model1,model2}
   GET /api/v1/monitoring/device/{pk}/nearby-devices/?distance__lte={distance}

List wifi session
#################

.. code-block:: text

   GET /api/v1/monitoring/wifi-session/

**Available filters**

The list of wifi session provides the following filters:

- ``device__organization`` (Organization ID of the device)
- ``device``  (Device ID)
- ``device__group``  (Device group ID)
- ``start_time`` (Start time of the wifi session)
- ``stop_time`` (Stop time of the wifi session)

Here's a few examples:

.. code-block:: text

   GET /api/v1/monitoring/wifi-session/?device__organization={organization_id}
   GET /api/v1/monitoring/wifi-session/?device={device_id}
   GET /api/v1/monitoring/wifi-session/?device__group={group_id}
   GET /api/v1/monitoring/wifi-session/?start_time={stop_time}
   GET /api/v1/monitoring/wifi-session/?stop_time={stop_time}

**Note:** Both `start_time` and `stop_time` support
greater than or equal to, as well as less than or equal to, filter lookups.

For example:

.. code-block:: text

   GET /api/v1/monitoring/wifi-session/?start_time__gt={start_time}
   GET /api/v1/monitoring/wifi-session/?start_time__gte={start_time}
   GET /api/v1/monitoring/wifi-session/?stop_time__lt={stop_time}
   GET /api/v1/monitoring/wifi-session/?stop_time__lte={stop_time}

Get wifi session
################

.. code-block:: text

   GET /api/v1/monitoring/wifi-session/{id}/

Pagination
##########

Wifi session endpoint support the ``page_size`` parameter
that allows paginating the results in conjunction with the page parameter.

.. code-block:: text

   GET /api/v1/monitoring/wifi-session/?page_size=10
   GET /api/v1/monitoring/wifi-session/?page_size=10&page=1

Signals
-------

``device_metrics_received``
~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Path**: ``openwisp_monitoring.device.signals.device_metrics_received``

**Arguments**:

- ``instance``: instance of ``Device`` whose metrics have been received
- ``request``: the HTTP request object
- ``time``: time with which metrics will be saved. If none, then server time will be used
- ``current``: whether the data has just been collected or was collected previously and sent now due to network connectivity issues

This signal is emitted when device metrics are received to the ``DeviceMetric``
view (only when using HTTP POST).

The signal is emitted just before a successful response is returned,
it is not sent if the response was not successful.

``health_status_changed``
~~~~~~~~~~~~~~~~~~~~~~~~~

**Path**: ``openwisp_monitoring.device.signals.health_status_changed``

**Arguments**:

- ``instance``: instance of ``DeviceMonitoring`` whose status has been changed
- ``status``: the status by which DeviceMonitoring's existing status has been updated with

This signal is emitted only if the health status of DeviceMonitoring object gets updated.

``threshold_crossed``
~~~~~~~~~~~~~~~~~~~~~

**Path**: ``openwisp_monitoring.monitoring.signals.threshold_crossed``

**Arguments**:

- ``metric``: ``Metric`` object whose threshold defined in related alert settings was crossed
- ``alert_settings``: ``AlertSettings`` related to the ``Metric``
- ``target``: related ``Device`` object
- ``first_time``: it will be set to true when the metric is written for the first time. It shall be set to false afterwards.
- ``tolerance_crossed``: it will be set to true if the metric has crossed the threshold for tolerance configured in alert settings.
  Otherwise, it will be set to false.

``first_time`` parameter can be used to avoid initiating unneeded actions.
For example, sending recovery notifications.

This signal is emitted when the threshold value of a ``Metric`` defined in
alert settings is crossed.

``pre_metric_write``
~~~~~~~~~~~~~~~~~~~~

**Path**: ``openwisp_monitoring.monitoring.signals.pre_metric_write``

**Arguments**:

- ``metric``: ``Metric`` object whose data shall be stored in timeseries database
- ``values``: metric data that shall be stored in the timeseries database
- ``time``: time with which metrics will be saved
- ``current``: whether the data has just been collected or was collected previously and sent now due to network connectivity issues

This signal is emitted for every metric before the write operation is sent to
the timeseries database.

``post_metric_write``
~~~~~~~~~~~~~~~~~~~~~

**Path**: ``openwisp_monitoring.monitoring.signals.post_metric_write``

**Arguments**:

- ``metric``: ``Metric`` object whose data is being stored in timeseries database
- ``values``: metric data that is being stored in the timeseries database
- ``time``: time with which metrics will be saved
- ``current``: whether the data has just been collected or was collected previously and sent now due to network connectivity issues

This signal is emitted for every metric after the write operation is successfully
executed in the background.

Management commands
-------------------

``run_checks``
~~~~~~~~~~~~~~

This command will execute all the `available checks <#available-checks>`_ for all the devices.
By default checks are run periodically by *celery beat*. You can learn more
about this in `Setup <#setup-integrate-in-an-existing-django-project>`_.

Example usage:

.. code-block:: shell

    cd tests/
    ./manage.py run_checks

``migrate_timeseries``
~~~~~~~~~~~~~~~~~~~~~~

This command triggers asynchronous migration of the time-series database.

Example usage:

.. code-block:: shell

    cd tests/
    ./manage.py migrate_timeseries

Monitoring scripts
------------------

Monitoring scripts are now deprecated in favour of `monitoring packages <https://github.com/openwisp/openwrt-openwisp-monitoring#openwrt-openwisp-monitoring>`_.
Follow the migration guide in `Migrating from monitoring scripts to monitoring packages <#migrating-from-monitoring-scripts-to-monitoring-packages>`_
section of this documentation.

Migrating from monitoring scripts to monitoring packages
--------------------------------------------------------

This section is intended for existing users of *openwisp-monitoring*.
The older version of *openwisp-monitoring* used *monitoring scripts* that
are now deprecated in favour of `monitoring packages <https://github.com/openwisp/openwrt-openwisp-monitoring#openwrt-openwisp-monitoring>`_.

If you already had a *monitoring template* created on your installation,
then the migrations of *openwisp-monitoring* will update that template
by making the following changes:

- The file name of all scripts will be appended with ``legacy-`` keyword
  in order to differentiate them from the scripts bundled with the new packages.
- The ``/usr/sbin/legacy-openwisp-monitoring`` (previously ``/usr/sbin/openwisp-monitoring``)
  script will be updated to exit if `openwisp-monitoring package <https://github.com/openwisp/openwrt-openwisp-monitoring#openwrt-openwisp-monitoring>`_
  is installed on the device.

Install the `monitoring packages <https://github.com/openwisp/openwrt-openwisp-monitoring#openwrt-openwisp-monitoring>`_
as mentioned in the `Install monitoring packages on device <#install-monitoring-packages-on-the-device>`_
section of this documentation.

After the proper configuration of the `openwisp-monitoring package <https://github.com/openwisp/openwrt-openwisp-monitoring#openwrt-openwisp-monitoring>`_
on your device, you can remove the monitoring template from your devices.

We suggest removing the monitoring template from the devices one at a time instead
of deleting the template. This ensures the correctness of
*openwisp monitoring package* configuration and you'll not miss out on
any monitoring data.

**Note:** If you have made changes to the default monitoring template created
by *openwisp-monitoring* or you are using custom monitoring templates, then you should
remove such templates from the device before installing the
`monitoring packages <https://github.com/openwisp/openwrt-openwisp-monitoring#openwrt-openwisp-monitoring>`_.

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
        'nested_admin',
    ]

For more information about how to work with django projects and django apps,
please refer to the `"Tutorial: Writing your first Django app" in the django docunmentation <https://docs.djangoproject.com/en/dev/intro/tutorial01/>`_.

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
    DEVICE_MONITORING_WIFICLIENT_MODEL = 'YOUR_MODULE_NAME.WifiClient'
    DEVICE_MONITORING_WIFISESSION_MODEL = 'YOUR_MODULE_NAME.WifiSession'

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

    from openwisp_monitoring.device.admin import DeviceAdmin, WifiSessionAdmin

    DeviceAdmin.list_display.insert(1, 'my_custom_field')
    DeviceAdmin.ordering = ['-my_custom_field']
    WifiSessionAdmin.fields += ['my_custom_field']

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

    Check = load_model('check', 'Check')

    admin.site.unregister(Check)

    @admin.register(Check)
    class CheckAdmin(BaseCheckAdmin):
        # add your changes here

For ``device_monitoring`` app,

.. code-block:: python

    from django.contrib import admin

    from openwisp_monitoring.device_monitoring.admin import DeviceAdmin as BaseDeviceAdmin
    from openwisp_monitoring.device_monitoring.admin import WifiSessionAdmin as BaseWifiSessionAdmin
    from swapper import load_model

    Device = load_model('config', 'Device')
    WifiSession = load_model('device_monitoring', 'WifiSession')

    admin.site.unregister(Device)
    admin.site.unregister(WifiSession)

    @admin.register(Device)
    class DeviceAdmin(BaseDeviceAdmin):
        # add your changes here

    @admin.register(WifiSession)
    class WifiSessionAdmin(BaseWifiSessionAdmin):
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

Step 1. Import and extend view:

.. code-block:: python

    # mydevice/api/views.py
    from openwisp_monitoring.device.api.views import (
        DeviceMetricView as BaseDeviceMetricView
    )

    class DeviceMetricView(BaseDeviceMetricView):
        # add your customizations here ...
        pass

Step 2: remove the following line from your root ``urls.py`` file:

.. code-block:: python

    re_path(
        'api/v1/monitoring/device/(?P<pk>[^/]+)/$',
        views.device_metric,
        name='api_device_metric',
    ),

Step 3: add an URL route pointing to your custom view in ``urls.py`` file:

.. code-block:: python

    # urls.py
    from mydevice.api.views import DeviceMetricView

    urlpatterns = [
        # ... other URLs
        re_path(r'^(?P<path>.*)$', DeviceMetricView.as_view(), name='api_device_metric',),
    ]

Contributing
------------

Please refer to the `OpenWISP contributing guidelines <http://openwisp.io/docs/developer/contributing.html>`_.
