Geographic & Indoor Maps
========================

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.3/intro.gif
    :target: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.3/intro.gif
    :alt: Intro

OpenWISP provides a unified web interface to monitor network status across
all scales: start with a global geographic overview, drill down into
specific buildings via indoor maps, and switch between floors to track
devices in real time.

.. contents:: **Table of contents**:
    :depth: 1
    :local:

.. _monitoring_dashboard_map:

Dashboard Map
-------------

The dashboard map shows locations with installed devices and provides a
visual overview of their monitoring status. It is controlled by the boolean
``OPENWISP_MONITORING_DASHBOARD_MAP`` setting, which defaults to ``True``.

The dashboard map requires ``OPENWISP_ADMIN_DASHBOARD_ENABLED`` from
:ref:`openwisp-utils <utils_admin_dashboard_enabled>` to be set to ``True``.
Set ``OPENWISP_MONITORING_DASHBOARD_MAP`` to ``False`` to disable the map if
you do not use OpenWISP geographic features.

When a location contains multiple devices, its marker reflects the most
common active health status. Deactivated devices are excluded from this
calculation. If the most common statuses are tied, a tie including ``ok`` or
``problem`` is shown as ``problem``; a tie between ``critical`` and
``unknown`` is shown as ``critical``.

Indoor Map View with Floor Navigation
-------------------------------------

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.3/indoor-map-view.gif
    :target: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.3/indoor-map-view.gif
    :alt: Indoor map view

The dashboard map includes an indoor view with floor switching and
full-screen mode.

Shareable Geographic Map URLs
-----------------------------

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.3/bookmark-url-map.gif
    :target: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.3/bookmark-url-map.gif
    :alt: Shareable Geographic Map URLs

Interactions with location or device nodes on the geographic map update
the URL, which can be bookmarked or shared.

Shareable Indoor Map URLs
-------------------------

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.3/bookmark-url-indoor-map.gif
    :target: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.3/bookmark-url-indoor-map.gif
    :alt: Shareable Indoor Map URLs

Interactions with indoor device nodes update the URL, which can be
bookmarked or shared.

Jump from Device Detail to General Map
--------------------------------------

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.3/view-on-general-map-button.gif
    :target: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.3/view-on-general-map-button.gif
    :alt: Location View from Device Details Page

Easily jump from the device detail page to the full geographic map, where
the current device is already in focus and nearby devices are visible.

Jump from Device Detail to Full Indoor View
-------------------------------------------

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.3/view-on-indoor-map-button.gif
    :target: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.3/view-on-indoor-map-button.gif
    :alt: Indoor Device View from Device Details Page

Easily jump from the device detail page to the full indoor map, where the
current device is already in focus and nearby devices are visible.

Real-Time Device Position Updates
---------------------------------

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.3/moving-devices.gif
    :target: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.3/moving-devices.gif
    :alt: Real-Time Device Position Updates

Device positions on the map are updated when new location data is
received.

Real-time map updates are delivered using WebSocket connections, allowing
the frontend to receive live location data without polling. The common
location broadcast channel is available at ``/ws/loci/location/`` and is
used to push device location updates to geographic map views as soon as
new data is received.

The location broadcast channel requires authentication. Access is
controlled based on organization membership:

- **Superusers:** Can receive location updates for all organizations.
- **Regular Users:** Can only receive location updates for organizations
  they manage.

This ensures that location data is properly scoped and users can only
receive real-time updates for locations within their managed
organizations.
