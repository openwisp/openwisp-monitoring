Changelog
=========

Version 0.2.0 [unreleased]
--------------------------

WIP.

Changes
~~~~~~~

Backward incompatible changes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- *Monitoring Template* is deprecated in favour of `openwisp monitoring packages <https://github.com/openwisp/openwrt-openwisp-monitoring#openwrt-openwisp-monitoring>`_.
  Follow the migration guide in `Migrating from monitoring scripts to monitoring packages <#migrating-from-monitoring-scripts-to-monitoring-packages>`_
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
- The `interface traffic <https://github.com/openwisp/openwisp-monitoring#traffic>`_
  and `associated WiFi clients <https://github.com/openwisp/openwisp-monitoring#wifi-clients>`_
  metrics store additional tags, i.e. ``organization_id``, ``location_id`` and ``floorplan_id``.

Version 0.1.0 [2021-01-31]
--------------------------

First release.
