from importlib import import_module

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError

TIMESERIES_DB = getattr(settings, 'TIMESERIES_DATABASE')


def load_backend(backend_name=TIMESERIES_DB['BACKEND'], module=None):
    """
    Returns database backend module given a fully qualified database backend name,
    or raise an error if it doesn't exist or backend is not well defined.
    """
    try:
        assert 'BACKEND' in TIMESERIES_DB, 'BACKEND'
        assert 'USER' in TIMESERIES_DB, 'USER'
        assert 'PASSWORD' in TIMESERIES_DB, 'PASSWORD'
        assert 'NAME' in TIMESERIES_DB, 'NAME'
        assert 'HOST' in TIMESERIES_DB, 'HOST'
        assert 'PORT' in TIMESERIES_DB, 'PORT'
        if module:
            return import_module(f'{backend_name}.{module}')
        else:
            return import_module(backend_name)
    except AttributeError as e:
        raise DatabaseError('No TIMESERIES_DATABASE specified in settings') from e
    except AssertionError as e:
        raise ImproperlyConfigured(
            f'"{e}" field is not declared in TIMESERIES_DATABASE'
        ) from e
    except ImportError as e:
        # The database backend wasn't found. Display a helpful error message
        # listing all built-in database backends.
        builtin_backends = ['influxdb']
        if backend_name not in [
            f'openwisp_monitoring.db.backends.{b}' for b in builtin_backends
        ]:
            raise ImproperlyConfigured(
                f"{backend_name} isn't an available database backend.\n"
                "Try using 'openwisp_monitoring.db.backends.XXX', where XXX is one of:\n"
                f"{builtin_backends}"
            ) from e


TimeseriesDB = load_backend(module='client').DatabaseClient
TimeseriesDBQueries = load_backend(module='queries')
