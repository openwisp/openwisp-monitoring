openwisp-monitoring
===================

------------

OpenWISP 2 monitoring module (Work in progress).

------------

.. contents:: **Table of Contents**:
   :backlinks: none
   :depth: 3

------------

Install Depdendencies
---------------------

`Install influxdb <https://docs.influxdata.com/influxdb/v1.4/introduction/installation/>`_ eg:

.. code-block:: shell

    curl -sL https://repos.influxdata.com/influxdb.key | sudo apt-key add -
    source /etc/lsb-release
    echo "deb https://repos.influxdata.com/${DISTRIB_ID,,} ${DISTRIB_CODENAME} stable" | sudo tee /etc/apt/sources.list.d/influxdb.list
    sudo apt-get update && sudo apt-get install influxdb
    sudo systemctl start influxdb

Install ``fping`` if you need to use the ping active check:

    sudo apt-get install fping

Setup (integrate in an existing django project)
-----------------------------------------------

Follow the setup instructions of `openwisp-controller
<https://github.com/openwisp/openwisp-controller>`_, then add the settings described below.

.. code-block:: python

    INSTALLED_APPS = [
        ...
        # openwisp monitoring
        'openwisp_monitoring.monitoring',
        'openwisp_monitoring.device',
        'notifications'
    ]

    INFLUXDB_USER = 'your influxdb user'
    INFLUXDB_PASSWORD = 'your influxdb password'
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

Installing for development
--------------------------

Install spatialite and sqlite:

.. code-block:: shell

    sudo apt-get install sqlite3 libsqlite3-dev openssl libssl-dev
    sudo apt-get install gdal-bin libproj-dev libgeos-dev libspatialite-dev

Install your forked repo:

.. code-block:: shell

    git clone git://github.com/<your_fork>/openwisp-monitoring
    cd openwisp-monitoring/
    python setup.py develop

Install test requirements:

.. code-block:: shell

    pip install -r requirements-test.txt

Create database:

.. code-block:: shell

    cd tests/
    ./manage.py migrate
    ./manage.py createsuperuser

Launch development server:

.. code-block:: shell

    ./manage.py runserver 0.0.0.0:8000

You can access the admin interface at http://127.0.0.1:8000/admin/.

Run tests with:

.. code-block:: shell

    ./runtests.py
