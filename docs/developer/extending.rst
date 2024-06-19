Extending OpenWISP Monitoring
=============================

.. include:: ../partials/developer-docs.rst

One of the core values of the OpenWISP project is `Software Reusability
<http://openwisp.io/docs/general/values.html#software-reusability-means-long-term-sustainability>`_,
for this reason *openwisp-monitoring* provides a set of base classes which
can be imported, extended and reused to create derivative apps.

In order to implement your custom version of *openwisp-monitoring*, you
need to perform the steps described in the rest of this section.

When in doubt, the code in the `test project
<https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/>`_
and the ``sample apps`` namely `sample_check
<https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/sample_check/>`_,
`sample_monitoring
<https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/sample_monitoring/>`_,
`sample_device_monitoring
<https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/sample_device_monitoring/>`_
will guide you in the correct direction: just replicate and adapt that
code to get a basic derivative of *openwisp-monitoring* working.

**Premise**: if you plan on using a customized version of this module, we
suggest to start with it since the beginning, because migrating your data
from the default module to your extended version may be time consuming.

1. Initialize your Custom Module
--------------------------------

The first thing you need to do in order to extend any
*openwisp-monitoring* app is create a new django app which will contain
your custom version of that *openwisp-monitoring* app.

A django app is nothing more than a `python package
<https://docs.python.org/3/tutorial/modules.html#packages>`_ (a directory
of python scripts), in the following examples we'll call these django apps
as ``mycheck``, ``mydevicemonitoring``, ``mymonitoring`` but you can name
it how you want:

.. code-block::

    django-admin startapp mycheck
    django-admin startapp mydevicemonitoring
    django-admin startapp mymonitoring

Keep in mind that the command mentioned above must be called from a
directory which is available in your `PYTHON_PATH
<https://docs.python.org/3/using/cmdline.html#envvar-PYTHONPATH>`_ so that
you can then import the result into your project.

Now you need to add ``mycheck`` to ``INSTALLED_APPS`` in your
``settings.py``, ensuring also that ``openwisp_monitoring.check`` has been
removed:

.. code-block:: python

    INSTALLED_APPS = [
        # ... other apps ...
        # 'openwisp_monitoring.check',        <-- comment out or delete this line
        # 'openwisp_monitoring.device',       <-- comment out or delete this line
        # 'openwisp_monitoring.monitoring'    <-- comment out or delete this line
        "mycheck",
        "mydevicemonitoring",
        "mymonitoring",
        "nested_admin",
    ]

For more information about how to work with django projects and django
apps, please refer to the `"Tutorial: Writing your first Django app" in
the django documentation
<https://docs.djangoproject.com/en/4.2/intro/tutorial01/>`_.

2. Install ``openwisp-monitoring``
----------------------------------

Install (and add to the requirement of your project)
*openwisp-monitoring*:

.. code-block::

    pip install --U https://github.com/openwisp/openwisp-monitoring/tarball/master

3. Add ``EXTENDED_APPS``
------------------------

Add the following to your ``settings.py``:

.. code-block:: python

    EXTENDED_APPS = ["device_monitoring", "monitoring", "check"]

4. Add ``openwisp_utils.staticfiles.DependencyFinder``
------------------------------------------------------

Add ``openwisp_utils.staticfiles.DependencyFinder`` to
``STATICFILES_FINDERS`` in your ``settings.py``:

.. code-block:: python

    STATICFILES_FINDERS = [
        "django.contrib.staticfiles.finders.FileSystemFinder",
        "django.contrib.staticfiles.finders.AppDirectoriesFinder",
        "openwisp_utils.staticfiles.DependencyFinder",
    ]

5. Add ``openwisp_utils.loaders.DependencyLoader``
--------------------------------------------------

Add ``openwisp_utils.loaders.DependencyLoader`` to ``TEMPLATES`` in your
``settings.py``:

.. code-block:: python

    TEMPLATES = [
        {
            "BACKEND": "django.template.backends.django.DjangoTemplates",
            "OPTIONS": {
                "loaders": [
                    "django.template.loaders.filesystem.Loader",
                    "django.template.loaders.app_directories.Loader",
                    "openwisp_utils.loaders.DependencyLoader",
                ],
                "context_processors": [
                    "django.template.context_processors.debug",
                    "django.template.context_processors.request",
                    "django.contrib.auth.context_processors.auth",
                    "django.contrib.messages.context_processors.messages",
                ],
            },
        }
    ]

6. Inherit the AppConfig Class
------------------------------

Please refer to the following files in the sample app of the test project:

- `sample_check/__init__.py
  <https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/sample_check/__init__.py>`_.
- `sample_check/apps.py
  <https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/sample_check/apps.py>`_.
- `sample_monitoring/__init__.py
  <https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/sample_monitoring/__init__.py>`_.
- `sample_monitoring/apps.py
  <https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/sample_monitoring/apps.py>`_.
- `sample_device_monitoring/__init__.py
  <https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/sample_device_monitoring/__init__.py>`_.
- `sample_device_monitoring/apps.py
  <https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/sample_device_monitoring/apps.py>`_.

For more information regarding the concept of ``AppConfig`` please refer
to the `"Applications" section in the django documentation
<https://docs.djangoproject.com/en/4.2/ref/applications/>`_.

7. Create your Custom Models
----------------------------

To extend ``check`` app, refer to `sample_check models.py file
<https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/sample_check/models.py>`_.

To extend ``monitoring`` app, refer to `sample_monitoring models.py file
<https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/sample_monitoring/models.py>`_.

To extend ``device_monitoring`` app, refer to `sample_device_monitoring
models.py file
<https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/sample_device_monitoring/models.py>`_.

.. note::

    - For doubts regarding how to use, extend or develop models please
      refer to the `"Models" section in the django documentation
      <https://docs.djangoproject.com/en/4.2/topics/db/models/>`_.
    - For doubts regarding proxy models please refer to `proxy models
      <https://docs.djangoproject.com/en/4.2/topics/db/models/#proxy-models>`_.

8. Add Swapper Configurations
-----------------------------

Add the following to your ``settings.py``:

.. code-block:: python

    # Setting models for swapper module
    # For extending check app
    CHECK_CHECK_MODEL = "YOUR_MODULE_NAME.Check"
    # For extending monitoring app
    MONITORING_CHART_MODEL = "YOUR_MODULE_NAME.Chart"
    MONITORING_METRIC_MODEL = "YOUR_MODULE_NAME.Metric"
    MONITORING_ALERTSETTINGS_MODEL = "YOUR_MODULE_NAME.AlertSettings"
    # For extending device_monitoring app
    DEVICE_MONITORING_DEVICEDATA_MODEL = "YOUR_MODULE_NAME.DeviceData"
    DEVICE_MONITORING_DEVICEMONITORING_MODEL = (
        "YOUR_MODULE_NAME.DeviceMonitoring"
    )
    DEVICE_MONITORING_WIFICLIENT_MODEL = "YOUR_MODULE_NAME.WifiClient"
    DEVICE_MONITORING_WIFISESSION_MODEL = "YOUR_MODULE_NAME.WifiSession"

Substitute ``<YOUR_MODULE_NAME>`` with your actual django app name (also
known as ``app_label``).

9. Create Database Migrations
-----------------------------

Create and apply database migrations:

.. code-block::

    ./manage.py makemigrations
    ./manage.py migrate

For more information, refer to the `"Migrations" section in the django
documentation
<https://docs.djangoproject.com/en/4.2/topics/migrations/>`_.

10. Create your Custom Admin
----------------------------

To extend ``check`` app, refer to `sample_check admin.py file
<https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/sample_check/admin.py>`_.

To extend ``monitoring`` app, refer to `sample_monitoring admin.py file
<https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/sample_monitoring/admin.py>`_.

To extend ``device_monitoring`` app, refer to `sample_device_monitoring
admin.py file
<https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/sample_device_monitoring/admin.py>`_.

To introduce changes to the admin, you can do it in the two ways described
below.

.. note::

    For doubts regarding how the django admin works, or how it can be
    customized, please refer to `"The django admin site" section in the
    django documentation
    <https://docs.djangoproject.com/en/4.2/ref/contrib/admin/>`_.

1. Monkey Patching
~~~~~~~~~~~~~~~~~~

If the changes you need to add are relatively small, you can resort to
monkey patching.

For example, for ``check`` app you can do it as:

.. code-block:: python

    from openwisp_monitoring.check.admin import CheckAdmin

    CheckAdmin.list_display.insert(1, "my_custom_field")
    CheckAdmin.ordering = ["-my_custom_field"]

Similarly for ``device_monitoring`` app, you can do it as:

.. code-block:: python

    from openwisp_monitoring.device.admin import DeviceAdmin, WifiSessionAdmin

    DeviceAdmin.list_display.insert(1, "my_custom_field")
    DeviceAdmin.ordering = ["-my_custom_field"]
    WifiSessionAdmin.fields += ["my_custom_field"]

Similarly for ``monitoring`` app, you can do it as:

.. code-block:: python

    from openwisp_monitoring.monitoring.admin import (
        MetricAdmin,
        AlertSettingsAdmin,
    )

    MetricAdmin.list_display.insert(1, "my_custom_field")
    MetricAdmin.ordering = ["-my_custom_field"]
    AlertSettingsAdmin.list_display.insert(1, "my_custom_field")
    AlertSettingsAdmin.ordering = ["-my_custom_field"]

2. Inheriting Admin Classes
~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you need to introduce significant changes and/or you don't want to
resort to monkey patching, you can proceed as follows:

For ``check`` app,

.. code-block:: python

    from django.contrib import admin

    from openwisp_monitoring.check.admin import CheckAdmin as BaseCheckAdmin
    from swapper import load_model

    Check = load_model("check", "Check")

    admin.site.unregister(Check)


    @admin.register(Check)
    class CheckAdmin(BaseCheckAdmin):
        # add your changes here
        pass

For ``device_monitoring`` app,

.. code-block:: python

    from django.contrib import admin

    from openwisp_monitoring.device_monitoring.admin import (
        DeviceAdmin as BaseDeviceAdmin,
    )
    from openwisp_monitoring.device_monitoring.admin import (
        WifiSessionAdmin as BaseWifiSessionAdmin,
    )
    from swapper import load_model

    Device = load_model("config", "Device")
    WifiSession = load_model("device_monitoring", "WifiSession")

    admin.site.unregister(Device)
    admin.site.unregister(WifiSession)


    @admin.register(Device)
    class DeviceAdmin(BaseDeviceAdmin):
        # add your changes here
        pass


    @admin.register(WifiSession)
    class WifiSessionAdmin(BaseWifiSessionAdmin):
        # add your changes here
        pass

For ``monitoring`` app,

.. code-block:: python

    from django.contrib import admin

    from openwisp_monitoring.monitoring.admin import (
        AlertSettingsAdmin as BaseAlertSettingsAdmin,
        MetricAdmin as BaseMetricAdmin,
    )
    from swapper import load_model

    Metric = load_model("Metric")
    AlertSettings = load_model("AlertSettings")

    admin.site.unregister(Metric)
    admin.site.unregister(AlertSettings)


    @admin.register(Metric)
    class MetricAdmin(BaseMetricAdmin):
        # add your changes here
        pass


    @admin.register(AlertSettings)
    class AlertSettingsAdmin(BaseAlertSettingsAdmin):
        # add your changes here
        pass

11. Create Root URL Configuration
---------------------------------

Please refer to the `urls.py
<https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/urls.py>`_
file in the test project.

For more information about URL configuration in django, please refer to
the `"URL dispatcher" section in the django documentation
<https://docs.djangoproject.com/en/4.2/topics/http/urls/>`_.

12. Create ``celery.py``
------------------------

Please refer to the `celery.py
<https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/celery.py>`_
file in the test project.

For more information about the usage of celery in django, please refer to
the `"First steps with Django" section in the celery documentation
<https://docs.celeryproject.org/en/master/django/first-steps-with-django.html>`_.

13. Import Celery Tasks
-----------------------

Add the following in your settings.py to import celery tasks from
``device_monitoring`` app.

.. code-block:: python

    CELERY_IMPORTS = ("openwisp_monitoring.device.tasks",)

14. Create the Custom Command ``run_checks``
--------------------------------------------

Please refer to the `run_checks.py
<https://github.com/openwisp/openwisp-monitoring/tree/master/tests/openwisp2/sample_check/management/commands/run_checks.py>`_
file in the test project.

For more information about the usage of custom management commands in
django, please refer to the `"Writing custom django-admin commands"
section in the django documentation
<https://docs.djangoproject.com/en/4.2/howto/custom-management-commands/>`_.

15. Import the Automated Tests
------------------------------

When developing a custom application based on this module, it's a good
idea to import and run the base tests too, so that you can be sure the
changes you're introducing are not breaking some of the existing features
of openwisp-monitoring.

In case you need to add breaking changes, you can overwrite the tests
defined in the base classes to test your own behavior.

For, extending ``check`` app see the `tests of sample_check app
<https://github.com/openwisp/openwisp-monitoring/blob/master/tests/openwisp2/sample_check/tests.py>`_
to find out how to do this.

For, extending ``device_monitoring`` app see the `tests of
sample_device_monitoring app
<https://github.com/openwisp/openwisp-monitoring/blob/master/tests/openwisp2/sample_device_monitoring/tests.py>`_
to find out how to do this.

For, extending ``monitoring`` app see the `tests of sample_monitoring app
<https://github.com/openwisp/openwisp-monitoring/blob/master/tests/openwisp2/sample_monitoring/tests.py>`_
to find out how to do this.

Other Base Classes that can be Inherited and Extended
-----------------------------------------------------

**The following steps are not required and are intended for more advanced
customization.**

``DeviceMetricView``
~~~~~~~~~~~~~~~~~~~~

This view is responsible for displaying ``Charts`` and ``Status``
primarily.

The full python path is:
``openwisp_monitoring.device.api.views.DeviceMetricView``.

If you want to extend this view, you will have to perform the additional
steps below.

Step 1. Import and extend view:

.. code-block:: python

    # mydevice/api/views.py
    from openwisp_monitoring.device.api.views import (
        DeviceMetricView as BaseDeviceMetricView,
    )


    class DeviceMetricView(BaseDeviceMetricView):
        # add your customizations here ...
        pass

Step 2: remove the following line from your root ``urls.py`` file:

.. code-block:: python

    re_path(
        "api/v1/monitoring/device/(?P<pk>[^/]+)/$",
        views.device_metric,
        name="api_device_metric",
    ),

Step 3: add an URL route pointing to your custom view in ``urls.py`` file:

.. code-block:: python

    # urls.py
    from mydevice.api.views import DeviceMetricView

    urlpatterns = [
        # ... other URLs
        re_path(
            r"^(?P<path>.*)$",
            DeviceMetricView.as_view(),
            name="api_device_metric",
        ),
    ]
