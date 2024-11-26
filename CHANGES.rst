Changelog
=========

Version 1.1.1 [2024-11-26]
--------------------------

Bugfixes
~~~~~~~~

- Fixed a backward compatibility issue with custom health status labels:
  previously, if customized health status labels
  (``OPENWISP_MONITORING_HEALTH_STATUS_LABELS``) were used and the new
  "deactivated" status label was missing after an upgrade, the application
  would crash during startup. In this version, a default set of valid
  labels is always available, which is then overridden by custom labels as
  needed.

Version 1.1.0 [2024-11-22]
--------------------------

Features
~~~~~~~~

- Added support for `monitoring WiFi clients and sessions
  <https://openwisp.io/docs/dev/monitoring/user/wifi-sessions.html>`_.
- Enabled importing and exporting of devices.
- Introduced `dashboard monitoring charts
  <https://openwisp.io/docs/dev/monitoring/user/dashboard-monitoring-charts.html>`_.
- Added support for the `Iperf3 check
  <https://openwisp.io/docs/dev/monitoring/user/checks.html#iperf3>`_.
- Introduced the `OPENWISP_MONITORING_DEFAULT_RETENTION_POLICY
  <https://openwisp.io/docs/dev/monitoring/user/settings.html#openwisp-monitoring-default-retention-policy>`_
  setting to configure the default retention policy.
- Added support for `InfluxDB UDP mode
  <https://openwisp.io/docs/dev/monitoring/user/settings.html#timeseries-backend-options>`_.
- Enabled filtering by custom date ranges for timeseries charts.
- Added zoom functionality to timeseries charts for detailed views.
- Introduced device deactivation: checks and monitoring data are not
  collected for deactivated devices.
- Disabled organization: checks and monitoring data are not collected for
  devices in disabled organization.
- Added WiFi version capability to the WiFi interface status.
- Added support for WiFi 6 client capability.
- Expanded REST API with device list and detailed monitoring information.
- Introduced an API endpoint to return nearby devices.
- Added an organization filter to timeseries charts.

Changes
~~~~~~~

- Display total values in traffic charts.
- Automatically delete timeseries data when a device is deleted.
- Removed squashed migrations for improved manageability.
- Fallback to `OPENWISP_CONTROLLER_MANAGEMENT_IP_ONLY
  <https://openwisp.io/docs/dev/controller/user/settings.html#openwisp-controller-management-ip-only>`_
  if `OPENWISP_MONITORING_MANAGEMENT_IP_ONLY
  <https://openwisp.io/docs/dev/monitoring/user/settings.html#openwisp-monitoring-management-ip-only>`_
  is not configured.
- Enhanced the efficiency of ``DeviceMetricView`` by batching write
  operations.
- Delegated timeseries data writing to a Celery worker in
  ``DeviceMetricView``.
- Introduced default timeouts for Celery tasks.
- Renamed the "Uptime" chart to "Ping Success Rate."
- Improved the UX of the device "Status" tab by making bridge members
  clickable.

Dependencies
++++++++++++

- Bumped ``openwisp-controller~=1.1.0``
- Bumped ``influxdb~=5.3.2``
- Bumped ``django-nested-admin~=4.0.2``
- Bumped ``python-dateutil>=2.7.0,<3.0.0``
- Added support for Django ``4.1.x`` and ``4.2.x``.
- Added support for Python ``3.10``.
- Dropped support for Python ``3.7``.
- Dropped support for Django ``3.0.x`` and ``3.1.x``.

Bugfixes
~~~~~~~~

- Fixed visibility of the "Recover deleted devices" button.
- Prevented chart loading failure when timezone JS fails.
- Corrected ping command from "-i" to "-p".
- Added error handling for ``IntegrityError`` in
  ``Metric._get_or_create``.
- Fixed unrecognized access technology exception.
- Displayed error messages from the timeseries chart API in an alert box.
- Fixed timeseries structure for storing signal metrics.
- Resolved data collection issues when tx/rx stats are missing.
- Used the "time" argument for calculating time in ``Chart._get_time``.

Version 1.0.3 [2022-12-29]
--------------------------

Bugfixes
~~~~~~~~

- Fixed data collection for missing mobile signal: Skip writing mobile
  signal metric if mobile signal info is missing.
- Fixed device health status changing to ``problem`` when the
  configuration status changes to ``modified``.

Version 1.0.2 [2022-08-04]
--------------------------

Bugfixes
~~~~~~~~

- Fixed migrations which create checks for existing devices; this problem
  was happening to OpenWISP instances which were deployed without OpenWISP
  Monitoring and then enabled the monitoring features

Version 1.0.1 [2022-07-01]
--------------------------

Bugfixes
~~~~~~~~

- Removed hardcoded static URLs which created issues when static files are
  served using an external service (e.g. S3 storage buckets)
- Fixed `"migrate_timeseries" command stalling when measurements exceeds
  retention policy
  <https://github.com/openwisp/openwisp-monitoring/issues/401>`_

Version 1.0.0 [2022-05-05]
--------------------------

Features
~~~~~~~~

- Added metrics for mobile (5G/LTE/UMTS/GSM) `signal strength
  <https://github.com/openwisp/openwisp-monitoring#mobile-signal-strength>`_,
  `signal quality
  <https://github.com/openwisp/openwisp-monitoring#mobile-signal-quality>`_
  and `mobile access technology in use
  <https://github.com/openwisp/openwisp-monitoring#mobile-access-technology-in-use>`_.
- Made `Ping check configurable
  <https://github.com/openwisp/openwisp-monitoring#openwisp_monitoring_ping_check_config>`_
- Added monitoring status chart to the dashboard and a geographic map
  which shows a visual representation of the monitoring the status of the
  devices.
- Added functionality to automatically clear the device's
  ``management_ip`` when a device goes offline
- Added support for specifying the time for received time-series data.
- Made read requests to timeseries DB resilient to failures

Changes
~~~~~~~

Backward incompatible changes
+++++++++++++++++++++++++++++

- *Monitoring Template* is removed in favour of `openwisp monitoring
  packages
  <https://github.com/openwisp/openwrt-openwisp-monitoring#openwrt-openwisp-monitoring>`_.
  Follow the migration guide in `migrating from monitoring scripts to
  monitoring packages
  <https://github.com/openwisp/openwisp-monitoring#migrating-from-monitoring-scripts-to-monitoring-packages>`_
  section of openwisp-monitoring documentation.
- If you have made changes to the default *Monitoring Template*, then
  create a backup of your template before running migrations. Running
  migrations will make changes to the default *Monitoring Template*.
- The time-series database schema for storing `interface traffic
  <https://github.com/openwisp/openwisp-monitoring#traffic>`_ and
  `associated WiFi clients
  <https://github.com/openwisp/openwisp-monitoring#wifi-clients>`_ has
  been updated. The data for *interface traffic* and *associated WiFi
  clients* is stored in ``traffic`` and ``wifi_clients`` measurements
  respectively. The Django migrations will perform the necessary
  operations in the time-series database aysnchronously. It is recommended
  that you backup the time-series database before running the migrations.

  You can use the `migrate_timeseries
  <https://github.com/openwisp/openwisp-monitoring#run-checks>`_
  management command to trigger the migration of the time-series database.

- The `interface traffic
  <https://github.com/openwisp/openwisp-monitoring#traffic>`_ and
  `associated WiFi clients
  <https://github.com/openwisp/openwisp-monitoring#wifi-clients>`_ metrics
  store additional tags, i.e. ``organization_id``, ``location_id`` and
  ``floorplan_id``.

Dependencies
++++++++++++

- Dropped support for Python 3.6
- Dropped support for Django 2.2
- Added support for Python 3.8 and 3.9
- Added support for Django 3.2 and 4.0
- Upgraded openwisp-controller to 1.0.x
- Upgraded inflxudb to 5.3.x
- Upgraded django-cache-memoize to 0.1.0
- Upgraded django-nested-admin to 3.4.0

Other changes
+++++++++++++

- *Configuration applied* check is triggered whenever the configuration
  status of a device changes
- Added a default ``5`` minutes tolerance to ``CPU`` and ``memory`` alert
  settings.
- Increased threshold value for ``disk`` alert settings from *80%* to
  *90%*, since some device models have limited flash and would trigger the
  alert in many cases.
- Renamed ``Check.check`` field to ``Check.check_type``
- Made metric health status independent of AlertSetting tolerance. Added
  ``tolerance_crossed`` parameter in
  ``openwisp_monitoring.monitoring.signals.threshold_crossed`` signal
- The system does not sends connection notifications if the connectivity
  of the device changes
- Improved UX of device's reachability (ping) chart. Added more colours to
  represent different scenarios
- Avoid showing charts which have empty data in the REST API response and
  in the device charts admin page

Bugfixes
~~~~~~~~

- Fixed a bug that caused inconsistency in the order of chart summary
  values
- Fixed bugs in restoring deleted devices using ``django-reversion``
- Fixed migrations referencing non-swappable OpenWISP modules that broke
  OpenWISP's extensibility
- Skip retry for writing metrics beyond retention policy. The celery
  worker kept on retrying writing data to InfluxDB even when the data
  points crossed the retention policy of InfluxDB. This led to
  accumulation of such tasks which overloaded the celery workers.

Version 0.1.0 [2021-01-31]
--------------------------

First release.
