openwisp-monitoring
===================

.. image:: https://github.com/openwisp/openwisp-monitoring/workflows/OpenWISP%20Monitoring%20CI%20Build/badge.svg?branch=master
    :target: https://github.com/openwisp/openwisp-monitoring/actions?query=workflow%3A%22OpenWISP+Monitoring+CI+Build%22
    :alt: CI build status

.. image:: https://coveralls.io/repos/github/openwisp/openwisp-monitoring/badge.svg?branch=master
    :target: https://coveralls.io/github/openwisp/openwisp-monitoring?branch=master
    :alt: Test coverage

.. image:: https://img.shields.io/librariesio/github/openwisp/openwisp-monitoring
    :target: https://libraries.io/github/openwisp/openwisp-monitoring#repository_dependencies
    :alt: Dependency monitoring

.. image:: https://badge.fury.io/py/openwisp-monitoring.svg
    :target: http://badge.fury.io/py/openwisp-monitoring
    :alt: pypi

.. image:: https://pepy.tech/badge/openwisp-monitoring
    :target: https://pepy.tech/project/openwisp-monitoring
    :alt: downloads

.. image:: https://img.shields.io/gitter/room/nwjs/nw.js.svg?style=flat-square
    :target: https://gitter.im/openwisp/monitoring
    :alt: support chat

.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
    :target: https://pypi.org/project/black/
    :alt: code style: black

.. image:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/monitoring-demo.gif
    :target: https://github.com/openwisp/openwisp-monitoring/tree/docs/docs/monitoring-demo.gif
    :alt: Feature Highlights

----

**Need a quick overview?** `Try the OpenWISP Demo
<https://openwisp.org/demo.html>`_.

OpenWISP Monitoring is a network monitoring system written in Python and
Django, designed to be **extensible**, **programmable**, **scalable** and
easy to use by end users: once the system is configured, monitoring
checks, alerts and metric collection happens automatically.

`OpenWISP <http://openwisp.org>`_ is not only an application designed for
end users, but can also be used as a framework on which custom network
automation solutions can be built on top of its building blocks.

Other popular building blocks that are part of the OpenWISP ecosystem are:

- `openwisp-controller <https://openwisp.io/docs/dev/controller/>`_:
  network and WiFi controller: provisioning, configuration management,
  x509 PKI management and more; works on OpenWrt, but designed to work
  also on other systems.
- `openwisp-network-topology
  <https://openwisp.io/docs/dev/network-topology/>`_: provides way to
  collect and visualize network topology data from dynamic mesh routing
  daemons or other network software (e.g.: OpenVPN); it can be used in
  conjunction with openwisp-monitoring to get a better idea of the state
  of the network
- `openwisp-firmware-upgrader
  <https://openwisp.io/docs/dev/firmware-upgrader/>`_: automated firmware
  upgrades (single device or mass network upgrades)
- `openwisp-radius <https://openwisp.io/docs/dev/user/radius.html>`_:
  based on FreeRADIUS, allows to implement network access authentication
  systems like 802.1x WPA2 Enterprise, captive portal authentication,
  Hotspot 2.0 (802.11u)
- `openwisp-ipam <https://openwisp.io/docs/dev/ipam/>`_: it allows to
  manage the IP address space of networks

**For a more complete overview of the OpenWISP modules and architecture**,
see the `OpenWISP Architecture Overview
<https://openwisp.io/docs/general/architecture.html>`_.

.. figure:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/dashboard.png
    :align: center

For a complete overview of features, refer to the `Monitoring: Features
<https://openwisp.io/docs/dev/monitoring/user/intro.html>`_ section of the
OpenWISP documentation.

Documentation
-------------

- `Usage documentation <https://openwisp.io/docs/dev/monitoring/>`_
- `Developer documentation
  <https://openwisp.io/docs/dev/monitoring/developer/>`_

Contributing
------------

Please refer to the `OpenWISP contributing guidelines
<http://openwisp.io/docs/developer/contributing.html>`_.
