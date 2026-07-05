import logging
from importlib import import_module

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError

from .base import BackendQueryBundle, BaseTimeseriesClient

logger = logging.getLogger(__name__)
BUILTIN_BACKENDS = ["influxdb", "influxdb2"]

TIMESERIES_DB = getattr(settings, "TIMESERIES_DATABASE", None)
if not TIMESERIES_DB:
    TIMESERIES_DB = {
        "BACKEND": "openwisp_monitoring.db.backends.influxdb",
        "USER": getattr(settings, "INFLUXDB_USER", "openwisp"),
        "PASSWORD": getattr(settings, "INFLUXDB_PASSWORD", "openwisp"),
        "NAME": getattr(settings, "INFLUXDB_DATABASE", "openwisp2"),
        "HOST": getattr(settings, "INFLUXDB_HOST", "localhost"),
        "PORT": getattr(settings, "INFLUXDB_PORT", "8086"),
    }
    logger.warning(
        "The previous method to define Timeseries Database has been deprecated. Please refer to the docs:\n"
        "https://github.com/openwisp/openwisp-monitoring#setup-integrate-in-an-existing-django-project"
    )


def load_backend(backend_name=TIMESERIES_DB["BACKEND"], config=None):
    """Return a validated backend package module."""
    config = TIMESERIES_DB if config is None else config
    try:
        backend_module = import_module(backend_name)
    except AttributeError as e:
        raise DatabaseError("No TIMESERIES_DATABASE specified in settings") from e
    except ImportError as e:
        # The database backend wasn't found. Display a helpful error message
        # listing all built-in database backends.
        if backend_name not in [
            f"openwisp_monitoring.db.backends.{b}" for b in BUILTIN_BACKENDS
        ]:
            raise ImproperlyConfigured(
                f"{backend_name} isn't an available database backend.\n"
                "Try using 'openwisp_monitoring.db.backends.XXX', where XXX is one of:\n"
                f"{BUILTIN_BACKENDS}"
            ) from e
        raise
    client_class = getattr(backend_module, "DatabaseClient", None)
    if not isinstance(client_class, type) or not issubclass(
        client_class, BaseTimeseriesClient
    ):
        raise ImproperlyConfigured(
            f"{backend_name} must define a DatabaseClient subclassing "
            "BaseTimeseriesClient."
        )

    client_class.validate_settings(config)
    queries = getattr(backend_module, "queries", None)
    if not isinstance(queries, BackendQueryBundle):
        raise ImproperlyConfigured(
            f"{backend_name} must expose a BackendQueryBundle instance as 'queries'."
        )
    queries.validate(client_class.backend_name)
    return backend_module


def load_backend_module(backend_name=TIMESERIES_DB["BACKEND"], module=None):
    backend_module = load_backend(backend_name=backend_name)
    if module is None:
        return backend_module
    if module == "client":
        return import_module(f"{backend_name}.client")
    if module == "queries":
        return backend_module.queries
    return import_module(f"{backend_name}.{module}")


backend_module = load_backend()
timeseries_db = backend_module.DatabaseClient().attach_queries(backend_module.queries)
