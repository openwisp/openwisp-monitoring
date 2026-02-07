Geographic and Indoor Maps
==========================

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.3/intro.gif
    :alt: Intro

OpenWISP provides a unified web interface to monitor network status across
all scales: start with a global geographic overview, drill down into
specific buildings via indoor maps, and switch between floors to track
devices in real time.

- **Indoor Map View with Floor Navigation:** The dashboard map includes an
  indoor view with floor switching and fullscreen mode.

  .. image:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.3/indoor-map-view.gif
      :alt: Indoor map view

- **Location View on Dedicated Map Page from Device Details Page:** The
  device detail page provides navigation to a full-page geographic map for
  the associated location.

  .. image:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.3/view-on-general-map-button.gif
      :alt: Location View from Device Details Page

- **Indoor Device View on Dedicated Map Page from Device Details Page:**
  The device detail page provides navigation to a full-page indoor map
  showing the device position.

  .. image:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.3/view-on-indoor-map-button.gif
      :alt: Indoor Device View from Device Details Page

- **Shareable Geographic Map URLs:** Interactions with location or device
  nodes on the geographic map update the URL.

  .. image:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.3/bookmark-url-map.gif
      :alt: Shareable Geographic Map URLs

- **Shareable Indoor Map URLs:** Interactions with indoor device nodes
  update the URL.

  .. image:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.3/bookmark-url-indoor-map.gif
      :alt: Shareable Geographic Map URLs

- **Real-Time Device Position Updates:** Device positions on the map are
  updated when new location data is received.

  .. image:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.3/moving-devices.gif
      :alt: Real-Time Device Position Updates

- **WebSocket-Based Real-Time Location Updates:** Real-time map updates
  are delivered using WebSocket connections, allowing the frontend to
  receive live location data without polling. The common location
  broadcast channel is available at ``/ws/loci/location/`` and is used to
  push device location updates to geographic map views as soon as new data
  is received.
