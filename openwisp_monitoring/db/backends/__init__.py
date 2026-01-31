import logging
from importlib import import_module

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .registry import (
    BUILTIN_BACKENDS,
    DEFAULT_BACKEND_PATH,
    builtin_backend_paths,
    default_options_for_backend,
    required_keys_for_backend,
    resolve_backend_path,
)

logger = logging.getLogger(__name__)

CURRENT_BACKEND = DEFAULT_BACKEND_PATH
BUILTIN_BACKEND_KEYS = tuple(BUILTIN_BACKENDS.keys())


def _build_timeseries_db():
    """
    Build a FLAT TIMESERIES_DB dict (for backward compatibility).

    - If TIMESERIES_DATABASE is missing: use legacy INFLUXDB_* settings (deprecated)
    - If TIMESERIES_DATABASE exists: validate/normalize it and resolve BACKEND
    """
    raw = getattr(settings, "TIMESERIES_DATABASE", None)

    if not raw:
        backend_path = CURRENT_BACKEND
        defaults = default_options_for_backend(backend_path)
        cfg = {
            "BACKEND": backend_path,
            "USER": getattr(
                settings, "INFLUXDB_USER", defaults.get("USER", "openwisp")
            ),
            "PASSWORD": getattr(settings, "INFLUXDB_PASSWORD", "openwisp"),
            "NAME": getattr(
                settings, "INFLUXDB_DATABASE", defaults.get("NAME", "openwisp2")
            ),
            "HOST": getattr(
                settings, "INFLUXDB_HOST", defaults.get("HOST", "localhost")
            ),
            "PORT": getattr(settings, "INFLUXDB_PORT", defaults.get("PORT", "8086")),
            "OPTIONS": {},
        }
        logger.warning(
            "Timeseries Database definition method deprecated. "
            "Please refer to the docs:\n"
            "https://github.com/openwisp/openwisp-monitoring#setup-integrate-in-an-existing-django-project"
        )
        return cfg, "legacy INFLUXDB_* settings"

    # New path: TIMESERIES_DATABASE dict
    if not isinstance(raw, dict):
        raise ImproperlyConfigured("TIMESERIES_DATABASE must be a dictionary.")
    if "BACKEND" not in raw:
        raise ImproperlyConfigured('TIMESERIES_DATABASE must define "BACKEND".')

    backend_path = resolve_backend_path(raw["BACKEND"])

    cfg = {"BACKEND": backend_path}
    cfg.update(default_options_for_backend(backend_path))

    # Merge user overrides
    for k, v in raw.items():
        if k not in ("BACKEND", "OPTIONS"):
            cfg[k] = v

    # Normalize OPTIONS
    options = raw.get("OPTIONS") or {}
    if not isinstance(options, dict):
        raise ImproperlyConfigured(
            'TIMESERIES_DATABASE["OPTIONS"] must be a dictionary.'
        )
    cfg["OPTIONS"] = options

    return cfg, "settings.TIMESERIES_DATABASE"


TIMESERIES_DB, _TIMESERIES_DB_SOURCE = _build_timeseries_db()


def load_backend_module(backend_name=None, module=None):
    """
    Loads backend module (root or submodule).

    Backend-specific required keys are validated via registry (only for known built-ins).
    """
    backend_path = resolve_backend_path(backend_name or TIMESERIES_DB.get("BACKEND"))
    if not backend_path:
        raise ImproperlyConfigured('TIMESERIES_DATABASE must define "BACKEND".')

    # Validate required keys for built-in backends
    required = required_keys_for_backend(backend_path)
    missing = [k for k in required if k not in TIMESERIES_DB]
    if missing:
        raise ImproperlyConfigured(
            f"Missing required settings for {backend_path}: {', '.join(missing)} "
            f"(source: {_TIMESERIES_DB_SOURCE})."
        )

    try:
        if module:
            return import_module(f"{backend_path}.{module}")
        return import_module(backend_path)
    except ImportError as e:
        if backend_path not in builtin_backend_paths():
            raise ImproperlyConfigured(
                f"{backend_path} isn't an available database backend.\n"
                f"Try one of the built-in backends: {list(BUILTIN_BACKEND_KEYS)}"
            ) from e
        raise


timeseries_db = load_backend_module(module="client").DatabaseClient()
timeseries_db.queries = load_backend_module(module="queries")
