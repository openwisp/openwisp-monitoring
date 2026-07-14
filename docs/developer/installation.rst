Developer Installation Instructions
===================================

.. include:: ../partials/developer-docs.rst

.. contents:: **Table of contents**:
    :depth: 2
    :local:

Dependencies
------------

- Python >= 3.11
- InfluxDB 1.x or InfluxDB 2.x
- fping
- OpenSSL

Installing for Development
--------------------------

Install the system dependencies:

Install system packages:

.. code-block:: shell

    sudo apt update
    sudo apt install -y sqlite3 libsqlite3-dev openssl libssl-dev
    sudo apt install -y gdal-bin libproj-dev libgeos-dev libspatialite-dev libsqlite3-mod-spatialite
    sudo apt install -y fping
    sudo apt install -y chromium

Fork and clone the forked repository:

.. code-block:: shell

    git clone git://github.com/<your_fork>/openwisp-monitoring

Navigate into the cloned repository:

.. code-block:: shell

    cd openwisp-monitoring/

Start Redis and InfluxDB using Docker:

.. code-block:: shell

    docker compose up -d redis influxdb

If you want to use InfluxDB 2.x instead, start ``influxdb2``:

.. code-block:: shell

    docker compose up -d redis influxdb2

If you want to test InfluxDB 2.x with UDP writes, start ``telegraf`` as
well:

.. code-block:: shell

    docker compose up -d redis influxdb2 telegraf

Setup and activate a virtual-environment. (we'll be using `virtualenv
<https://pypi.org/project/virtualenv/>`_)

.. code-block:: shell

    python -m virtualenv env
    source env/bin/activate

Make sure that you are using pip version 20.2.4 before moving to the next
step:

.. code-block:: shell

    pip install -U pip wheel setuptools

Install development dependencies:

.. code-block:: shell

    pip install -e .
    pip install -r requirements-test.txt
    npm install -g prettier

If you are using InfluxDB 2.0, export the following environment variable
before running migrations, celery, or the development server:

.. code-block:: shell

    export TIMESERIES_BACKEND=influxdb2

If you are using the ``influxdb2`` and ``redis`` containers provided in
this repository's ``docker-compose.yml``, no additional variables are
needed because the default values in ``tests/openwisp2/settings.py``
already match that setup.

If you are not using the provided containers, or if you changed ports or
credentials, you can override the defaults with:

.. code-block:: shell

    # Optional overrides for non-default setups
    export INFLUXDB2_URL=http://localhost:8087
    export INFLUXDB2_USER=openwisp
    export INFLUXDB2_PASSWORD=openwisp-token
    export INFLUXDB2_BUCKET=openwisp2
    export REDIS_HOST=localhost

Install WebDriver for Chromium for your browser version from
https://chromedriver.chromium.org/home and extract ``chromedriver`` to one
of directories from your ``$PATH`` (example: ``~/.local/bin/``).

Create database:

.. code-block:: shell

    cd tests/
    ./manage.py migrate
    ./manage.py createsuperuser

Run celery and celery-beat with the following commands (separate terminal
windows are needed):

.. code-block:: shell

    cd tests/
    celery -A openwisp2 worker -l info
    celery -A openwisp2 beat -l info

Launch development server:

.. code-block:: shell

    ./manage.py runserver 0.0.0.0:8000

You can access the admin interface at ``http://127.0.0.1:8000/admin/``.

Run tests with (make sure you have the :ref:`selenium dependencies
<selenium_dependencies>` installed locally first):

.. code-block:: shell

    ./runtests  # default: runs tests with InfluxDB 1.x over HTTP
    TIMESERIES_UDP=1 ./runtests  # InfluxDB 1.x over UDP
    TSDB=influxdb2 ./runtests  # InfluxDB 2.x over HTTP
    TSDB=influxdb2 TIMESERIES_UDP=1 ./runtests  # InfluxDB 2.x over UDP (via Telegraf)

The ``./runtests`` script is the main test entry point. By default it runs
the InfluxDB test flow. Set ``TSDB=influxdb2`` to run the InfluxDB 2.x
test flow instead. Set ``TIMESERIES_UDP=1`` to run the UDP flow for the
selected backend. When using ``TSDB=influxdb2 TIMESERIES_UDP=1``, Telegraf
must be running because InfluxDB 2.x does not support UDP natively. Using
``--parallel`` is not supported in this module.

Run quality assurance tests with:

.. code-block:: shell

    ./run-qa-checks

Alternative Sources
-------------------

PyPI
~~~~

To install the latest Pypi:

.. code-block:: shell

    pip install openwisp-monitoring

Github
~~~~~~

To install the latest development version tarball via HTTPs:

.. code-block:: shell

    pip install https://github.com/openwisp/openwisp-monitoring/tarball/master

Alternatively you can use the git protocol:

.. code-block:: shell

    pip install -e git+git://github.com/openwisp/openwisp-monitoring#egg=openwisp_monitoring

Install and Run on Docker
-------------------------

.. warning::

    This Docker image is for development purposes only.

    For the official OpenWISP Docker images, see: :doc:`/docker/index`.

Build from the Dockerfile:

.. code-block:: shell

    docker compose build

Run the docker container:

.. code-block:: shell

    docker compose up

By default, the Docker setup uses InfluxDB 1.8. To use InfluxDB 2.9
instead, run:

.. code-block:: shell

    TIMESERIES_BACKEND=influxdb2 docker compose up
