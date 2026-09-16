import atexit
from importlib import import_module

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .base import BackendQueryBundle, BaseTimeseriesClient

BUILTIN_BACKENDS = ["influxdb", "influxdb2", "elasticsearch"]


def get_timeseries_database():
    timeseries_database = getattr(settings, "TIMESERIES_DATABASE", None)
    if not timeseries_database:
        raise ImproperlyConfigured("TIMESERIES_DATABASE must be configured.")
    return timeseries_database


TIMESERIES_DB = get_timeseries_database()


def _is_missing_backend_module(error, backend_name):
    missing_module = getattr(error, "name", None)
    return isinstance(error, ModuleNotFoundError) and (
        missing_module == backend_name or backend_name.startswith(f"{missing_module}.")
    )


def _resolve_backend_name(backend_name=None, config=None):
    if backend_name is None:
        config = TIMESERIES_DB if config is None else config
        backend_name = config.get("BACKEND") if hasattr(config, "get") else None
    if not backend_name:
        raise ImproperlyConfigured(
            '"BACKEND" field is not declared in TIMESERIES_DATABASE'
        )
    return backend_name


def load_backend(backend_name=None, config=None):
    """Return a validated backend package module."""
    config = TIMESERIES_DB if config is None else config
    backend_name = _resolve_backend_name(backend_name, config)
    try:
        backend_module = import_module(backend_name)
    except ImportError as e:
        # The database backend wasn't found. Display a helpful error message
        # listing all built-in database backends.
        if _is_missing_backend_module(e, backend_name) and backend_name not in [
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


def load_backend_module(backend_name=None, module=None):
    backend_name = _resolve_backend_name(backend_name)
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

if timeseries_db.backend_name == "influxdb2" and callable(
    getattr(timeseries_db, "close", None)
):
    atexit.register(timeseries_db.close)
