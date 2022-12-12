Changelog
=========

Version 1.0.3 [2022-12-29]
--------------------------

Bugfixes
~~~~~~~~

- Fixed data collection for missing mobile signal:
  Skip writing mobile signal metric if mobile signal
  info is missing.
- Fixed device health status changing to ``problem``
  when the configuration status changes to ``modified``.

Version 1.0.2 [2022-08-04]
--------------------------

Bugfixes
~~~~~~~~

- Fixed migrations which create checks for existing devices;
  this problem was happening to OpenWISP instances which were
  deployed without OpenWISP Monitoring and then enabled
  the monitoring features

Version 1.0.1 [2022-07-01]
--------------------------

Bugfixes
~~~~~~~~

- Removed hardcoded static URLs which created
  issues when static files are served using an
  external service (e.g. S3 storage buckets)
- Fixed `"migrate_timeseries" command stalling
  when measurements exceeds retention policy
  <https://github.com/openwisp/openwisp-monitoring/issues/401>`_

Version 1.0.0 [2022-05-05]
--------------------------

Features
~~~~~~~~

- Added metrics for mobile (5G/LTE/UMTS/GSM)
  `signal strength <https://github.com/openwisp/openwisp-monitoring#mobile-signal-strength>`_,
  `signal quality <https://github.com/openwisp/openwisp-monitoring#mobile-signal-quality>`_
  and `mobile access technology in use
  <https://github.com/openwisp/openwisp-monitoring#mobile-access-technology-in-use>`_.
- Made `Ping check configurable <https://github.com/openwisp/openwisp-monitoring#openwisp_monitoring_ping_check_config>`_
- Added monitoring status chart to the dashboard and
  a geographic map which shows a visual representation of the
  monitoring the status of the devices.
- Added functionality to automatically clear the device's ``management_ip``
  when a device goes offline
- Added support for specifying the time for received time-series data.
- Made read requests to timeseries DB resilient to failures

Changes
~~~~~~~

Backward incompatible changes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- *Monitoring Template* is removed in favour of
  `openwisp monitoring packages <https://github.com/openwisp/openwrt-openwisp-monitoring#openwrt-openwisp-monitoring>`_.
  Follow the migration guide in `migrating from monitoring scripts to
  monitoring packages <https://github.com/openwisp/openwisp-monitoring#migrating-from-monitoring-scripts-to-monitoring-packages>`_
  section of openwisp-monitoring documentation.
- If you have made changes to the default *Monitoring Template*, then
  create a backup of your template before running migrations. Running
  migrations will make changes to the default *Monitoring Template*.
- The time-series database schema for storing
  `interface traffic <https://github.com/openwisp/openwisp-monitoring#traffic>`_
  and `associated WiFi clients <https://github.com/openwisp/openwisp-monitoring#wifi-clients>`_
  has been updated. The data for *interface traffic* and *associated WiFi clients*
  is stored in ``traffic`` and ``wifi_clients`` measurements respectively.
  The Django migrations will perform the necessary operations in the time-series
  database aysnchronously. It is recommended that you backup the time-series
  database before running the migrations.

  You can use the `migrate_timeseries <https://github.com/openwisp/openwisp-monitoring#run-checks>`_
  management command to trigger the migration of the time-series database.
- The `interface traffic <https://github.com/openwisp/openwisp-monitoring#traffic>`_
  and `associated WiFi clients <https://github.com/openwisp/openwisp-monitoring#wifi-clients>`_
  metrics store additional tags, i.e. ``organization_id``, ``location_id`` and ``floorplan_id``.

Dependencies
^^^^^^^^^^^^

- Dropped support for Python 3.6
- Dropped support for Django 2.2
- Added support for Python 3.8 and 3.9
- Added support for Django 3.2 and 4.0
- Upgraded openwisp-controller to 1.0.x
- Upgraded inflxudb to 5.3.x
- Upgraded django-cache-memoize to 0.1.0
- Upgraded django-nested-admin to 3.4.0

Other changes
^^^^^^^^^^^^^

- *Configuration applied* check is triggered whenever the
  configuration status of a device changes
- Added a default ``5`` minutes tolerance to ``CPU`` and ``memory``
  alert settings.
- Increased threshold value for ``disk`` alert settings from
  *80%* to *90%*, since some device models have limited flash and
  would trigger the alert in many cases.
- Renamed ``Check.check`` field to ``Check.check_type``
- Made metric health status independent of AlertSetting tolerance.
  Added ``tolerance_crossed`` parameter in
  ``openwisp_monitoring.monitoring.signals.threshold_crossed`` signal
- The system does not sends connection notifications if the
  connectivity of the device changes
- Improved UX of device's reachability (ping) chart.
  Added more colours to represent different scenarios
- Avoid showing charts which have empty data in the REST API response
  and in the device charts admin page

Bugfixes
~~~~~~~~

- Fixed a bug that caused inconsistency in the order of chart summary values
- Fixed bugs in restoring deleted devices using ``django-reversion``
- Fixed migrations referencing non-swappable OpenWISP modules
  that broke OpenWISP's extensibility
- Skip retry for writing metrics beyond retention policy.
  The celery worker kept on retrying writing data to InfluxDB even
  when the data points crossed the retention policy of InfluxDB. This
  led to accumulation of such tasks which overloaded the celery workers.

Version 0.1.0 [2021-01-31]
--------------------------

First release.
