Installation instructions
=========================

.. include:: /partials/developers-docs-warning.rst

Deploy it in production
-----------------------

See:

- `ansible-openwisp2 <https://github.com/openwisp/ansible-openwisp2>`_
- `docker-openwisp <https://github.com/openwisp/docker-openwisp>`_

.. _setup-integrate-in-an-existing-django-project:

Install system dependencies
---------------------------

*openwisp-monitoring* uses InfluxDB to store metrics. Follow the
`installation instructions from InfluxDB's official documentation
<https://docs.influxdata.com/influxdb/v1.8/introduction/install/>`_.

.. important::

    Only *InfluxDB 1.8.x* is supported in *openwisp-monitoring*.

Install system packages:

.. code-block:: shell

    sudo apt install -y openssl libssl-dev \
                        gdal-bin libproj-dev libgeos-dev \
                        fping

Install stable version from PyPI
--------------------------------

Install from PyPI:

.. code-block:: shell

    pip install openwisp-monitoring

Install development version
---------------------------

Install tarball:

.. code-block:: shell

    pip install https://github.com/openwisp/openwisp-monitoring/tarball/master

Alternatively, you can install via pip using git:

.. code-block:: shell

    pip install -e git+git://github.com/openwisp/openwisp-monitoring#egg=openwisp_monitoring

If you want to contribute, follow the instructions in `"Installing for
development" <#installing-for-development>`_ section.

Installing for development
--------------------------

Install the system dependencies as mentioned in the `"Install system
dependencies" <#install-system-dependencies>`_ section. Install these
additional packages that are required for development:

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
    npm install -g jshint stylelint

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

You can access the admin interface at http://127.0.0.1:8000/admin/.

Run tests with:

.. code-block:: shell

    ./runtests.py  # using --parallel is not supported in this module

Run quality assurance tests with:

.. code-block:: shell

    ./run-qa-checks

Install and run on docker
-------------------------

.. note::

    This Docker image is for development purposes only. For the official
    OpenWISP Docker images, see: `docker-openwisp
    <https://github.com/openwisp/docker-openwisp>`_.

Build from the Dockerfile:

.. code-block:: shell

    docker-compose build

Run the docker container:

.. code-block:: shell

    docker-compose up
