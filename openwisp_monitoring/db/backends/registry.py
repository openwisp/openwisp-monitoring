from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class BackendSpec:
    path: str
    required_keys: Tuple[str, ...]
    default_options: Dict[str, object]


BUILTIN_BACKENDS: Dict[str, BackendSpec] = {
    "influxdb": BackendSpec(
        path="openwisp_monitoring.db.backends.influxdb",
        required_keys=("NAME", "HOST", "PORT", "USER", "PASSWORD"),
        default_options={
            "HOST": "localhost",
            "PORT": "8086",
            "NAME": "openwisp2",
            "USER": "openwisp",
        },
    )
}

DEFAULT_BACKEND_KEY = "influxdb"
DEFAULT_BACKEND_PATH = BUILTIN_BACKENDS[DEFAULT_BACKEND_KEY].path


def builtin_backend_paths() -> Tuple[str, ...]:
    return tuple(spec.path for spec in BUILTIN_BACKENDS.values())


def default_options_for_backend(backend_path: str) -> Dict[str, object]:
    for spec in BUILTIN_BACKENDS.values():
        if spec.path == backend_path:
            return dict(spec.default_options)
    return {}


def resolve_backend_path(backend_value: str) -> str:
    if backend_value in BUILTIN_BACKENDS:
        return BUILTIN_BACKENDS[backend_value].path
    return backend_value


def required_keys_for_backend(backend_path: str) -> Tuple[str, ...]:
    for spec in BUILTIN_BACKENDS.values():
        if spec.path == backend_path:
            return spec.required_keys
    return tuple()
