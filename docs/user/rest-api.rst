Rest API
--------

Live documentation
~~~~~~~~~~~~~~~~~~

.. image:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/api-doc.png

A general live API documentation (following the OpenAPI specification) at ``/api/v1/docs/``.

Browsable web interface
~~~~~~~~~~~~~~~~~~~~~~~

.. image:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/api-ui-1.png
.. image:: https://github.com/openwisp/openwisp-monitoring/raw/docs/docs/api-ui-2.png

Additionally, opening any of the endpoints `listed below <#list-of-endpoints>`_
directly in the browser will show the `browsable API interface of Django-REST-Framework
<https://www.django-rest-framework.org/topics/browsable-api/>`_,
which makes it even easier to find out the details of each endpoint.

List of endpoints
~~~~~~~~~~~~~~~~~

Since the detailed explanation is contained in the `Live documentation <#live-documentation>`_
and in the `Browsable web page <#browsable-web-interface>`_ of each point,
here we'll provide just a list of the available endpoints,
for further information please open the URL of the endpoint in your browser.

Retrieve general monitoring charts
##################################

.. code-block:: text

    GET /api/v1/monitoring/dashboard/

This API endpoint is used to show dashboard monitoring charts. It supports
multi-tenancy and allows filtering monitoring data by ``organization_slug``,
``location_id`` and ``floorplan_id`` e.g.:

.. code-block:: text

    GET /api/v1/monitoring/dashboard/?organization_slug=<org1-slug>,<org2-slug>&location_id=<location1-id>,<location2-id>&floorplan_id=<floorplan1-id>,<floorplan2-id>

- When retrieving chart data, the ``time`` parameter allows to specify
  the time frame, eg:

  - ``1d``: returns data of the last day
  - ``3d``: returns data of the last 3 days
  - ``7d``: returns data of the last 7 days
  - ``30d``: returns data of the last 30 days
  - ``365d``: returns data of the last 365 days

- In alternative to ``time`` it is possible to request chart data for a custom
  date range by using the ``start`` and ``end`` parameters, eg:

.. code-block:: text

    GET /api/v1/monitoring/dashboard/?start={start_datetime}&end={end_datetime}

**Note**: ``start`` and  ``end`` parameters should be in the format
``YYYY-MM-DD H:M:S``, otherwise 400 Bad Response will be returned.

Retrieve device charts and device status data
#############################################

.. code-block:: text

    GET /api/v1/monitoring/device/{pk}/?key={key}&status=true&time={timeframe}

The format used for Device Status is inspired by
`NetJSON DeviceMonitoring <http://netjson.org/docs/what.html#devicemonitoring>`_.

**Notes**:

- If the request is made without ``?status=true`` the response will
  contain only charts data and will not include any device status information
  (current load average, ARP table, DCHP leases, etc.).

- When retrieving chart data, the ``time`` parameter allows to specify
  the time frame, eg:

  - ``1d``: returns data of the last day
  - ``3d``: returns data of the last 3 days
  - ``7d``: returns data of the last 7 days
  - ``30d``: returns data of the last 30 days
  - ``365d``: returns data of the last 365 days

- In alternative to ``time`` it is possible to request chart data for a custom
  date range by using the ``start`` and ``end`` parameters, eg:

- The response contains device information, monitoring status (health status),
  a list of metrics with their respective statuses, chart data and
  device status information (only if ``?status=true``).

- This endpoint can be accessed with session authentication, token authentication,
  or alternatively with the device key passed as query string parameter
  as shown below (`?key={key}`);
  note: this method is meant to be used by the devices.

.. code-block:: text

    GET /api/v1/monitoring/device/{pk}/?key={key}&status=true&start={start_datetime}&end={end_datetime}

**Note**: ``start`` and  ``end`` parameters must be in the format
``YYYY-MM-DD H:M:S``, otherwise 400 Bad Response will be returned.

List device monitoring information
##################################

.. code-block:: text

    GET /api/v1/monitoring/device/

**Notes**:

- The response contains device information and monitoring status (health status),
  but it does not include the information and
  health status of the specific metrics, this information
  can be retrieved in the detail endpoint of each device.

- This endpoint can be accessed with session authentication and token authentication.

**Available filters**

Data can be filtered by health status (e.g. critical, ok, problem, and unknown)
to obtain the list of devices in the corresponding status, for example,
to retrieve the list of devices which are in critical conditions
(eg: unreachable), the following will work:

.. code-block:: text

   GET /api/v1/monitoring/device/?monitoring__status=critical

To filter a list of device monitoring data based
on their organization, you can use the ``organization_id``.

.. code-block:: text

   GET /api/v1/monitoring/device/?organization={organization_id}

To filter a list of device monitoring data based
on their organization slug, you can use the ``organization_slug``.

.. code-block:: text

   GET /api/v1/monitoring/device/?organization_slug={organization_slug}

Collect device metrics and status
#################################

.. code-block:: text

    POST /api/v1/monitoring/device/{pk}/?key={key}&time={datetime}

If data is latest then an additional parameter current can also be passed. For e.g.:

.. code-block:: text

    POST /api/v1/monitoring/device/{pk}/?key={key}&time={datetime}&current=true

The format used for Device Status is inspired by
`NetJSON DeviceMonitoring <http://netjson.org/docs/what.html#devicemonitoring>`_.

**Note**: the device data will be saved in the timeseries database using
the date time specified ``time``, this should be in the format
``%d-%m-%Y_%H:%M:%S.%f``, otherwise 400 Bad Response will be returned.

If the request is made without passing the ``time`` argument,
the server local time will be used.

The ``time`` parameter was added to support `resilient collection
and sending of data by the OpenWISP Monitoring Agent
<https://github.com/openwisp/openwrt-openwisp-monitoring#collecting-vs-sending>`_,
this feature allows sending data collected while the device is offline.

List nearby devices
###################

.. code-block:: text

    GET /api/v1/monitoring/device/{pk}/nearby-devices/

Returns list of nearby devices along with respective distance (in metres) and
monitoring status.

**Available filters**

The list of nearby devices provides the following filters:

- ``organization`` (Organization ID of the device)
- ``organization__slug``  (Organization slug of the device)
- ``monitoring__status``  (Monitoring status (``unknown``, ``ok``, ``problem``, or ``critical``))
- ``model`` (Pipe `|` separated list of device models)
- ``distance__lte`` (Distance in metres)

Here's a few examples:

.. code-block:: text

   GET /api/v1/monitoring/device/{pk}/nearby-devices/?organization={organization_id}
   GET /api/v1/monitoring/device/{pk}/nearby-devices/?organization__slug={organization_slug}
   GET /api/v1/monitoring/device/{pk}/nearby-devices/?monitoring__status={monitoring_status}
   GET /api/v1/monitoring/device/{pk}/nearby-devices/?model={model1,model2}
   GET /api/v1/monitoring/device/{pk}/nearby-devices/?distance__lte={distance}

List wifi session
#################

.. code-block:: text

   GET /api/v1/monitoring/wifi-session/

**Available filters**

The list of wifi session provides the following filters:

- ``device__organization`` (Organization ID of the device)
- ``device``  (Device ID)
- ``device__group``  (Device group ID)
- ``start_time`` (Start time of the wifi session)
- ``stop_time`` (Stop time of the wifi session)

Here's a few examples:

.. code-block:: text

   GET /api/v1/monitoring/wifi-session/?device__organization={organization_id}
   GET /api/v1/monitoring/wifi-session/?device={device_id}
   GET /api/v1/monitoring/wifi-session/?device__group={group_id}
   GET /api/v1/monitoring/wifi-session/?start_time={stop_time}
   GET /api/v1/monitoring/wifi-session/?stop_time={stop_time}

**Note:** Both `start_time` and `stop_time` support
greater than or equal to, as well as less than or equal to, filter lookups.

For example:

.. code-block:: text

   GET /api/v1/monitoring/wifi-session/?start_time__gt={start_time}
   GET /api/v1/monitoring/wifi-session/?start_time__gte={start_time}
   GET /api/v1/monitoring/wifi-session/?stop_time__lt={stop_time}
   GET /api/v1/monitoring/wifi-session/?stop_time__lte={stop_time}

Get wifi session
################

.. code-block:: text

   GET /api/v1/monitoring/wifi-session/{id}/

Pagination
##########

Wifi session endpoint support the ``page_size`` parameter
that allows paginating the results in conjunction with the page parameter.

.. code-block:: text

   GET /api/v1/monitoring/wifi-session/?page_size=10
   GET /api/v1/monitoring/wifi-session/?page_size=10&page=1
