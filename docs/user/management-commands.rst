Management Commands
===================

.. _run_checks:

``run_checks``
--------------

This command will execute all the :doc:`available checks <checks>` for all
the devices. By default checks are run periodically by *celery beat*.

Example usage:

.. code-block:: shell

    cd tests/
    ./manage.py run_checks

``migrate_timeseries``
----------------------

This command triggers asynchronous migration of the time-series database.

Example usage:

.. code-block:: shell

    cd tests/
    ./manage.py migrate_timeseries
