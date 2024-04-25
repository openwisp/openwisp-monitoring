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
