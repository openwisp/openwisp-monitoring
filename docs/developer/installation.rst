Developer Installation Instructions
===================================

.. include:: ../partials/developer-docs.rst

.. contents:: **Table of contents**:
    :depth: 2
    :local:

Dependencies
------------

- Python >= 3.8
- InfluxDB 1.8
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

You can access the admin interface at ``http://127.0.0.1:8000/admin/``.

Run tests with:

.. code-block:: shell

    ./runtests.py  # using --parallel is not supported in this module

Run quality assurance tests with:

.. code-block:: shell

    ./run-qa-checks

Alternative Sources
-------------------

PyPI
~~~~

To install the latest stable version from pypi:

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

    docker-compose build

Run the docker container:

.. code-block:: shell

    docker-compose up
