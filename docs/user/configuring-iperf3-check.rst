Configuring Iperf3 Check
========================

.. contents:: **Table of contents**:
    :depth: 2
    :local:

1. Make Sure Iperf3 is Installed on the Device
----------------------------------------------

Register your device to OpenWISP and make sure the `iperf3 openwrt package
<https://openwrt.org/packages/pkgdata/iperf3>`_ is installed on the
device, eg:

.. code-block:: shell

    opkg install iperf3  # if using without authentication
    opkg install iperf3-ssl  # if using with authentication (read below for more info)

2. Ensure SSH Access from OpenWISP is Enabled on your Devices
-------------------------------------------------------------

Follow the steps in :doc:`"Configuring Push Operations"
</controller/user/push-operations>` section of the documentation to allow
SSH access to you device from OpenWISP.

.. important::

    Make sure device connection is enabled & working with right update
    strategy i.e. ``OpenWrt SSH``.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.1/enable-openwrt-ssh.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.1/enable-openwrt-ssh.png
    :alt: Enable ssh access from openwisp to device
    :align: center

3. Set Up and Configure Iperf3 Server Settings
----------------------------------------------

After having deployed your Iperf3 servers, you need to configure the
iperf3 settings on the django side of OpenWISP, see the `test project
settings for reference
<https://github.com/openwisp/openwisp-monitoring/blob/master/tests/openwisp2/settings.py>`_.

The host can be specified by hostname, IPv4 literal, or IPv6 literal.
Example:

.. code-block:: python

    OPENWISP_MONITORING_IPERF3_CHECK_CONFIG = {
        # 'org_pk' : {'host' : [], 'client_options' : {}}
        "a9734710-db30-46b0-a2fc-01f01046fe4f": {
            # Some public iperf3 servers
            # https://iperf.fr/iperf-servers.php#public-servers
            "host": ["iperf3.openwisp.io", "2001:db8::1", "192.168.5.2"],
            "client_options": {
                "port": 5209,
                "udp": {"bitrate": "30M"},
                "tcp": {"bitrate": "0"},
            },
        },
        # another org
        "b9734710-db30-46b0-a2fc-01f01046fe4f": {
            # available iperf3 servers
            "host": ["iperf3.openwisp2.io", "192.168.5.3"],
            "client_options": {
                "port": 5207,
                "udp": {"bitrate": "50M"},
                "tcp": {"bitrate": "20M"},
            },
        },
    }

.. note::

    If an organization has more than one iperf3 server configured, then it
    enables the iperf3 checks to run concurrently on different devices. If
    all of the available servers are busy, then it will add the check back
    in the queue.

The celery-beat configuration for the iperf3 check needs to be added too:

.. code-block:: python

    from celery.schedules import crontab

    # Celery TIME_ZONE should be equal to django TIME_ZONE
    # In order to schedule run_iperf3_checks on the correct time intervals
    CELERY_TIMEZONE = TIME_ZONE
    CELERY_BEAT_SCHEDULE = {
        # Other celery beat configurations
        # Celery beat configuration for iperf3 check
        "run_iperf3_checks": {
            "task": "openwisp_monitoring.check.tasks.run_checks",
            # https://docs.celeryq.dev/en/latest/userguide/periodic-tasks.html#crontab-schedules
            # Executes check every 5 mins from 00:00 AM to 6:00 AM (night)
            "schedule": crontab(minute="*/5", hour="0-6"),
            # Iperf3 check path
            "args": (["openwisp_monitoring.check.classes.Iperf3"],),
            "relative": True,
        }
    }

Once the changes are saved, you will need to restart all the processes.

.. note::

    We recommended to configure this check to run in non peak traffic
    times to not interfere with standard traffic.

4. Run the Check
----------------

This should happen automatically if you have celery-beat correctly
configured and running in the background. For testing purposes, you can
run this check manually using the :ref:`run_checks <run_checks>` command.

After that, you should see the iperf3 network measurements charts.

.. image:: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.1/iperf3-charts.png
    :target: https://raw.githubusercontent.com/openwisp/openwisp-monitoring/docs/docs/1.1/iperf3-charts.png
    :alt: Iperf3 network measurement charts

.. _iperf3_check_parameters:

Iperf3 Check Parameters
-----------------------

Currently, iperf3 check supports the following parameters:

================== ======== =========================================
**Parameter**      **Type** **Default Value**
``host``           ``list`` ``[]``
``username``       ``str``  ``''``
``password``       ``str``  ``''``
``rsa_public_key`` ``str``  ``''``
``client_options`` ``dict`` Refer the :ref:`iperf3_client_parameters`
                            table below for available parameters
================== ======== =========================================

.. _iperf3_client_parameters:

Iperf3 Client Options
~~~~~~~~~~~~~~~~~~~~~

=================== ======== ==========================================
**Parameters**      **Type** **Default Value**
``port``            ``int``  ``5201``
``time``            ``int``  ``10``
``bytes``           ``str``  ``''``
``blockcount``      ``str``  ``''``
``window``          ``str``  ``0``
``parallel``        ``int``  ``1``
``reverse``         ``bool`` ``False``
``bidirectional``   ``bool`` ``False``
``connect_timeout`` ``int``  ``1000``
``tcp``             ``dict`` Refer the :ref:`iperf3_client_tcp_options`
                             table below for available parameters
``udp``             ``dict`` Refer the :ref:`iperf3_client_udp_options`
                             table below for available parameters
=================== ======== ==========================================

.. _iperf3_client_tcp_options:

Iperf3 Client's TCP Options
+++++++++++++++++++++++++++

============== ======== =================
**Parameters** **Type** **Default Value**
``bitrate``    ``str``  ``0``
``length``     ``str``  ``128K``
============== ======== =================

.. _iperf3_client_udp_options:

Iperf3 Client's UDP Options
+++++++++++++++++++++++++++

============== ======== =================
**Parameters** **Type** **Default Value**
``bitrate``    ``str``  ``30M``
``length``     ``str``  ``0``
============== ======== =================

To learn how to use these parameters, please see the :ref:`iperf3 check
configuration example <openwisp_monitoring_iperf3_check_config>`.

Visit the `official documentation <https://www.mankier.com/1/iperf3>`_ to
learn more about the iperf3 parameters.

Iperf3 Authentication
---------------------

By default iperf3 check runs without any kind of **authentication**, in
this section we will explain how to configure **RSA authentication**
between the **client** and the **server** to restrict connections to
authenticated clients.

Server Side
~~~~~~~~~~~

1. Generate RSA Keypair
+++++++++++++++++++++++

.. code-block:: shell

    openssl genrsa -des3 -out private.pem 2048
    openssl rsa -in private.pem -outform PEM -pubout -out public_key.pem
    openssl rsa -in private.pem -out private_key.pem -outform PEM

After running the commands mentioned above, the public key will be stored
in ``public_key.pem`` which will be used in **rsa_public_key** parameter
in :ref:`openwisp_monitoring_iperf3_check_config` and the private key will
be contained in the file ``private_key.pem`` which will be used with
**--rsa-private-key-path** command option when starting the iperf3 server.

2. Create User Credentials
++++++++++++++++++++++++++

.. code-block:: shell

    USER=iperfuser PASSWD=iperfpass
    echo -n "{$USER}$PASSWD" | sha256sum | awk '{ print $1 }'
    ----
    ee17a7f98cc87a6424fb52682396b2b6c058e9ab70e946188faa0714905771d7 #This is the hash of "iperfuser"

Add the above hash with username in ``credentials.csv``

.. code-block:: shell

    # file format: username,sha256
    iperfuser,ee17a7f98cc87a6424fb52682396b2b6c058e9ab70e946188faa0714905771d7

3. Now Start the Iperf3 Server with Auth Options
++++++++++++++++++++++++++++++++++++++++++++++++

.. code-block:: shell

    iperf3 -s --rsa-private-key-path ./private_key.pem --authorized-users-path ./credentials.csv

Client Side (OpenWrt Device)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Install iperf3-ssl
+++++++++++++++++++++

Install the `iperf3-ssl openwrt package
<https://openwrt.org/packages/pkgdata/iperf3-ssl>`_ instead of the normal
`iperf3 openwrt package <https://openwrt.org/packages/pkgdata/iperf3>`_
because the latter comes without support for authentication.

You may also check your installed **iperf3 openwrt package** features:

.. code-block:: shell

    root@vm-openwrt:- iperf3 -v
    iperf 3.7 (cJSON 1.5.2)
    Linux vm-openwrt 4.14.171 #0 SMP Thu Feb 27 21:05:12 2020 x86_64
    Optional features available: CPU affinity setting, IPv6 flow label, TCP congestion algorithm setting,
    sendfile / zerocopy, socket pacing, authentication # contains 'authentication'

.. _configure_iperf3_check_auth_parameters:

2. Configure Iperf3 Check Auth Parameters
+++++++++++++++++++++++++++++++++++++++++

Now, add the following iperf3 authentication parameters to
:ref:`openwisp_monitoring_iperf3_check_config` in the settings:

.. code-block:: python

    OPENWISP_MONITORING_IPERF3_CHECK_CONFIG = {
        "a9734710-db30-46b0-a2fc-01f01046fe4f": {
            "host": [
                "iperf1.openwisp.io",
                "iperf2.openwisp.io",
                "192.168.5.2",
            ],
            # All three parameters (username, password, rsa_publc_key)
            # are required for iperf3 authentication
            "username": "iperfuser",
            "password": "iperfpass",
            # Add RSA public key without any headers
            # ie. -----BEGIN PUBLIC KEY-----, -----BEGIN END KEY-----
            "rsa_public_key": (
                """
                MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAwuEm+iYrfSWJOupy6X3N
                dxZvUCxvmoL3uoGAs0O0Y32unUQrwcTIxudy38JSuCccD+k2Rf8S4WuZSiTxaoea
                6Du99YQGVZeY67uJ21SWFqWU+w6ONUj3TrNNWoICN7BXGLE2BbSBz9YaXefE3aqw
                GhEjQz364Itwm425vHn2MntSp0weWb4hUCjQUyyooRXPrFUGBOuY+VvAvMyAG4Uk
                msapnWnBSxXt7Tbb++A5XbOMdM2mwNYDEtkD5ksC/x3EVBrI9FvENsH9+u/8J9Mf
                2oPl4MnlCMY86MQypkeUn7eVWfDnseNky7TyC0/IgCXve/iaydCCFdkjyo1MTAA4
                BQIDAQAB
                """
            ),
            "client_options": {
                "port": 5209,
                "udp": {"bitrate": "20M"},
                "tcp": {"bitrate": "0"},
            },
        }
    }
