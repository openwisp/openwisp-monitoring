import logging
from importlib import import_module

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError

logger = logging.getLogger(__name__)

TIMESERIES_DB = getattr(settings, 'TIMESERIES_DATABASE', None)
if not TIMESERIES_DB:
    INFLUXDB_BACKEND = getattr(settings, 'INFLUXDB_BACKEND', 'openwisp_monitoring.db.backends.influxdb')

    if INFLUXDB_BACKEND == 'openwisp_monitoring.db.backends.influxdb':
        # InfluxDB 1.x configuration
        TIMESERIES_DB = {
            'BACKEND': INFLUXDB_BACKEND,
            'USER': getattr(settings, 'INFLUXDB_USER', 'openwisp'),
            'PASSWORD': getattr(settings, 'INFLUXDB_PASSWORD', 'openwisp'),
            'NAME': getattr(settings, 'INFLUXDB_DATABASE', 'openwisp2'),
            'HOST': getattr(settings, 'INFLUXDB_HOST', 'localhost'),
            'PORT': getattr(settings, 'INFLUXDB_PORT', '8086'),
        }
    elif INFLUXDB_BACKEND == 'openwisp_monitoring.db.backends.influxdb2':
        # InfluxDB 2.x configuration
        TIMESERIES_DB = {
            'BACKEND': INFLUXDB_BACKEND,
            'TOKEN': getattr(settings, 'INFLUXDB_TOKEN', 'dltiEmsmMKU__9SoBE0ingFdMTS3UksrESwIQDNtW_3WOgn8bQGdyYzPcx_aDtvZkqvR8RbMkwVVlzUJxpm62w=='),
            'ORG': getattr(settings, 'INFLUXDB_ORG', 'myorg'),
            'BUCKET': getattr(settings, 'INFLUXDB_BUCKET', 'mybucket'),
            'HOST': getattr(settings, 'INFLUXDB_HOST', 'localhost'),
            'PORT': getattr(settings, 'INFLUXDB_PORT', '8086'),
        }
    else:
        logger.warning('Invalid INFLUXDB_BACKEND setting. Please check the documentation.')

    if INFLUXDB_BACKEND == 'openwisp_monitoring.db.backends.influxdb':
        logger.warning(
            'The previous method to define Timeseries Database has been deprecated. Please refer to the docs:\n'
            'https://github.com/openwisp/openwisp-monitoring#setup-integrate-in-an-existing-django-project'
        )

def load_backend_module(backend_name=TIMESERIES_DB['BACKEND'], module=None):
    """
    Returns database backend module given a fully qualified database backend name,
    or raise an error if it doesn't exist or backend is not well defined.
    """
    try:
        assert 'BACKEND' in TIMESERIES_DB, 'BACKEND'
        is_influxdb2 = '2' in TIMESERIES_DB['BACKEND']
        if is_influxdb2:
            # InfluxDB 2.x specific checks
            assert 'TOKEN' in TIMESERIES_DB, 'TOKEN'
            assert 'ORG' in TIMESERIES_DB, 'ORG'
            assert 'BUCKET' in TIMESERIES_DB, 'BUCKET'
        else:
            # InfluxDB 1.x specific checks
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
        builtin_backends = ['influxdb', 'influxdb2']
        if backend_name not in [
            f'openwisp_monitoring.db.backends.{b}' for b in builtin_backends
        ]:
            raise ImproperlyConfigured(
                f"{backend_name} isn't an available database backend.\n"
                "Try using 'openwisp_monitoring.db.backends.XXX', where XXX is one of:\n"
                f"{builtin_backends}"
            ) from e
        else:
            raise e


if '2' in TIMESERIES_DB['BACKEND']:
    timeseries_db = load_backend_module(module='client').DatabaseClient(
        bucket=TIMESERIES_DB['BUCKET'],
        org=TIMESERIES_DB['ORG'],
        token=TIMESERIES_DB['TOKEN'],
        url=f"http://{TIMESERIES_DB['HOST']}:{TIMESERIES_DB['PORT']}",
    )
    timeseries_db.queries = load_backend_module(TIMESERIES_DB['BACKEND'], module='queries')
else:
    timeseries_db = load_backend_module(module='client').DatabaseClient()
    timeseries_db.queries = load_backend_module(module='queries')