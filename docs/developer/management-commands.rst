Management commands
-------------------

.. _run_checks:

``run_checks``
~~~~~~~~~~~~~~

This command will execute all the `available checks <available-checks>`_ for all the devices.
By default checks are run periodically by *celery beat*. You can learn more
about this in :ref:`Setup <setup-integrate-in-an-existing-django-project>`.

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
