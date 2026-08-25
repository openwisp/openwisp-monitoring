import logging
import re
from collections.abc import Iterator, Mapping, Sequence
from copy import deepcopy
from datetime import datetime, timezone
from itertools import count
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.utils.dateparse import parse_datetime
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from elasticsearch import (
    ApiError,
    ConflictError,
    Elasticsearch,
    NotFoundError,
    TransportError,
)
from elasticsearch.helpers import bulk

from openwisp_monitoring.utils import retry

from ...exceptions import TimeseriesWriteException
from .. import TIMESERIES_DB
from ..base import (
    BaseTimeseriesClient,
    BatchWritePayload,
    ChartQueryParams,
    FieldSelection,
    TimeseriesFields,
    TimeseriesPoint,
    TimeseriesTags,
)

logger = logging.getLogger(__name__)


class _SafeFormatDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


SeriesTags = dict[str, Any]
SeriesTagSet = frozenset[tuple[str, Any]]
SeriesKey = tuple[str, SeriesTags | None]
SeriesCache = dict[tuple[str, SeriesTagSet], list[TimeseriesPoint]]
_TIMESTAMP_PRECISION_MULTIPLIERS = {
    "s": 1,
    "ms": 1000,
    "u": 1000000,
    "ns": 1000000000,
}
_POINT_IDENTITY_FIELDS = (
    "__openwisp_time_key",
    "__openwisp_measurement_key",
    "__openwisp_tags_key",
)


def _normalize_datetime(value: datetime, precision="s"):
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    if precision is None:
        return value.isoformat().replace("+00:00", "Z")
    timestamp = value.timestamp()
    multiplier = _TIMESTAMP_PRECISION_MULTIPLIERS.get(precision)
    return int(timestamp * multiplier) if multiplier else timestamp


def _normalize_timestamp_value(value, precision="s"):
    if isinstance(value, datetime):
        return _normalize_datetime(value, precision=precision)
    if isinstance(value, str):
        parsed = parse_datetime(value)
        return _normalize_datetime(parsed, precision=precision) if parsed else value
    return value


class QueryResultSet:
    """ResultSet-like wrapper for Elasticsearch search responses."""

    def __init__(
        self, response: Mapping[str, Any], precision: str | None = "s"
    ) -> None:
        self.response = response
        self.precision = precision
        self._points: list[TimeseriesPoint] | None = None
        self._series_cache: SeriesCache | None = None

    def get(self, key, default=None):
        return self.response.get(key, default)

    def _normalize_time(self, value):
        return _normalize_timestamp_value(value, precision=self.precision)

    def _hits(self) -> list[Mapping[str, Any]]:
        return self.response.get("hits", {}).get("hits", [])

    def _build_points(self) -> list[TimeseriesPoint]:
        if self._points is not None:
            return self._points
        points = []
        for hit in self._hits():
            document = hit.get("_source") or {}
            base_point = {
                "time": self._normalize_time(document.get("@timestamp")),
                "__raw_time": document.get("@timestamp"),
                "_measurement": document.get("measurement", "results"),
            }
            base_point.update(document.get("tags") or {})
            fields = document.get("fields") or {}
            if not fields:
                points.append(base_point)
                continue
            for field_name, field_value in fields.items():
                points.append(
                    {
                        **base_point,
                        "_field": field_name,
                        "_value": field_value,
                    }
                )
        self._points = points
        return points

    def _group_by_measurement_tags(self) -> SeriesCache:
        if self._series_cache is not None:
            return self._series_cache
        series_dict: SeriesCache = {}
        special_fields = {"_measurement", "_field", "_value", "time", "__raw_time"}
        for point in self._build_points():
            measurement = point.get("_measurement", "results")
            tags = {
                key: value for key, value in point.items() if key not in special_fields
            }
            tags_key = frozenset(tags.items()) if tags else frozenset()
            series_dict.setdefault((measurement, tags_key), []).append(point)
        self._series_cache = series_dict
        return series_dict

    def get_points(
        self, measurement: str | None = None, tags: TimeseriesTags | None = None
    ) -> Iterator[TimeseriesPoint]:
        for (
            series_measurement,
            series_tags_frozen,
        ), points in self._group_by_measurement_tags().items():
            series_tags = dict(series_tags_frozen) if series_tags_frozen else {}
            if measurement is not None and measurement != series_measurement:
                continue
            if tags is not None and not self._tag_matches(series_tags, tags):
                continue
            yield from points

    def keys(self) -> list[SeriesKey]:
        return [
            (measurement, dict(tags_frozen) if tags_frozen else None)
            for measurement, tags_frozen in self._group_by_measurement_tags().keys()
        ]

    def items(self) -> list[tuple[SeriesKey, Iterator[TimeseriesPoint]]]:
        items = []
        for (
            measurement,
            tags_frozen,
        ), points in self._group_by_measurement_tags().items():
            tags = dict(tags_frozen) if tags_frozen else None
            items.append(((measurement, tags), (point for point in points)))
        return items

    @staticmethod
    def _tag_matches(series_tags: TimeseriesTags, filter_tags: TimeseriesTags) -> bool:
        for tag_name, tag_value in filter_tags.items():
            if series_tags.get(tag_name) != tag_value:
                return False
        return True

    def __iter__(self) -> Iterator[TimeseriesPoint]:
        yield from self.get_points()

    def __len__(self) -> int:
        return len(self.keys())

    def __repr__(self) -> str:
        items = []
        for key, points in self.items():
            items.append("'%s': %s" % (key, list(points)))
        return "ResultSet({%s})" % ", ".join(items)


class DatabaseClient(BaseTimeseriesClient):
    backend_name = "elasticsearch"
    client_error = TransportError
    required_settings = ("BACKEND", "NAME")
    requires_write_operation_id = True
    _INVALID_DATA_STREAM_NAME = re.compile(r'[\\/*?"<>| ,#:]')
    _MAX_DATA_STREAM_NAME_BYTES = 255
    _OPERATORS = ("=", "!=", "<", ">", "<=", ">=")
    _DURATION_PATTERN = re.compile(r"(?:\d+[smhdw])+")
    _DURATION_PART_PATTERN = re.compile(r"(\d+)([smhdw])")
    _DEFAULT_ROLLOVER_SECONDS = 30 * 24 * 60 * 60
    _PIT_KEEP_ALIVE = "1m"
    _DISTINCT_PAGE_SIZE = 1000
    # highest precision supported by the cardinality aggregation,
    # counts below this threshold are exact
    _CARDINALITY_PRECISION = 40000
    # Wins over broad external templates that may also match OpenWISP streams.
    _OPENWISP_INDEX_TEMPLATE_PRIORITY = 500
    _RESOURCE_METADATA_KEY = "openwisp_monitoring"
    _RESOURCE_DESCRIPTION = "OpenWISP Monitoring Elasticsearch data stream data"
    _INDEXED_FIELD_PATHS = {
        "keyword": "indexed_fields.keyword",
        "numeric": "indexed_fields.numeric",
        "boolean": "indexed_fields.boolean",
    }
    _CHART_FILTERS = (
        "content_type",
        "object_id",
        "ifname",
        "organization_id",
        "location_id",
        "floorplan_id",
    )

    @classmethod
    def validate_settings(cls, config: Mapping[str, Any] | None) -> Mapping[str, Any]:
        super().validate_settings(config)
        try:
            cls._validate_data_stream_name(config["NAME"])
        except ValueError as exception:
            raise ImproperlyConfigured(
                '"NAME" must be a valid Elasticsearch data stream name.'
            ) from exception
        has_cloud_id = bool(config.get("CLOUD_ID"))
        has_url = bool(config.get("URL"))
        has_host_port = all(config.get(field) for field in ("HOST", "PORT"))
        if not has_cloud_id and not has_url and not has_host_port:
            raise ImproperlyConfigured(
                'Elasticsearch TIMESERIES_DATABASE must define "CLOUD_ID", '
                '"URL", or both "HOST" and "PORT".'
            )
        if not isinstance(config.get("OPTIONS", {}), Mapping):
            raise ImproperlyConfigured('"OPTIONS" must be a mapping.')
        if "VERIFY_CERTS" in config and not isinstance(config["VERIFY_CERTS"], bool):
            raise ImproperlyConfigured('"VERIFY_CERTS" must be a boolean.')
        uses_basic_auth = not config.get("API_KEY") and not config.get("BEARER_AUTH")
        if uses_basic_auth and bool(config.get("USER")) != bool(config.get("PASSWORD")):
            raise ImproperlyConfigured(
                '"USER" and "PASSWORD" must be configured together.'
            )
        return config

    def __init__(self, db_name: str | None = None) -> None:
        self.db_name = self._validate_data_stream_name(
            TIMESERIES_DB["NAME"] if db_name is None else db_name
        )
        self._write_sequence = count()

    def _close_cached_client(self) -> None:
        client = self.__dict__.get("db")
        close = getattr(client, "close", None)
        try:
            if callable(close):
                close()
        except Exception as exception:
            logger.debug("Error while closing Elasticsearch client: %s", exception)

    def reset(self, db_name: str | None = None) -> None:
        if db_name is not None:
            self._validate_data_stream_name(db_name)
        self._close_cached_client()
        super().reset(db_name=db_name)
        self.__dict__.pop("db", None)
        self._write_sequence = count()

    def close(self) -> None:
        self.reset()

    @property
    def use_udp(self) -> bool:
        return False

    @cached_property
    def db(self) -> Elasticsearch:
        return Elasticsearch(**self._get_client_kwargs())

    @property
    def options(self) -> Mapping[str, Any]:
        return TIMESERIES_DB.get("OPTIONS", {})

    @property
    def refresh(self):
        return self.options.get("refresh", "wait_for")

    def _get_client_kwargs(self) -> dict[str, Any]:
        kwargs = {}
        url = None
        if TIMESERIES_DB.get("CLOUD_ID"):
            kwargs["cloud_id"] = TIMESERIES_DB["CLOUD_ID"]
        else:
            url = TIMESERIES_DB.get("URL")
            if not url:
                url = f"http://{TIMESERIES_DB['HOST']}:{TIMESERIES_DB['PORT']}"
            kwargs["hosts"] = [url]
        if TIMESERIES_DB.get("API_KEY"):
            kwargs["api_key"] = TIMESERIES_DB["API_KEY"]
        elif TIMESERIES_DB.get("BEARER_AUTH"):
            kwargs["bearer_auth"] = TIMESERIES_DB["BEARER_AUTH"]
        elif TIMESERIES_DB.get("USER") and TIMESERIES_DB.get("PASSWORD"):
            kwargs["basic_auth"] = (
                TIMESERIES_DB["USER"],
                TIMESERIES_DB["PASSWORD"],
            )
        credentials = kwargs.keys() & {"api_key", "bearer_auth", "basic_auth"}
        if credentials and url and urlparse(url).scheme == "http":
            logger.warning(
                'Sending Elasticsearch credentials over insecure HTTP at "%s". '
                'Consider switching TIMESERIES_DATABASE["URL"] to https:// when '
                "running outside local development.",
                url,
            )
        for setting_name, kwarg_name in (
            ("CA_CERTS", "ca_certs"),
            ("SSL_ASSERT_FINGERPRINT", "ssl_assert_fingerprint"),
            ("VERIFY_CERTS", "verify_certs"),
        ):
            if setting_name in TIMESERIES_DB:
                kwargs[kwarg_name] = TIMESERIES_DB[setting_name]
        for option_name in (
            "http_compress",
            "max_retries",
            "request_timeout",
            "retry_on_timeout",
        ):
            if option_name in self.options:
                kwargs[option_name] = self.options[option_name]
        return kwargs

    @classmethod
    def _validate_data_stream_name(cls, name: str) -> str:
        invalid = (
            not isinstance(name, str)
            or not name
            or name != name.lower()
            or name.startswith(("-", "_", "+", "."))
            or name in {".", ".."}
            or cls._INVALID_DATA_STREAM_NAME.search(name)
            or len(name.encode()) > cls._MAX_DATA_STREAM_NAME_BYTES
        )
        if invalid:
            raise ValueError(f'Invalid Elasticsearch data stream name "{name}"')
        return name

    def _get_retention_policy_name(self, retention_policy=None) -> str:
        if not retention_policy or retention_policy == "autogen":
            return "autogen"
        return str(retention_policy)

    def _get_stream_name(self, retention_policy=None) -> str:
        retention_policy = self._get_retention_policy_name(retention_policy)
        if retention_policy == "autogen":
            return self.db_name
        return self._validate_data_stream_name(f"{self.db_name}-{retention_policy}")

    def _get_policy_name(self, retention_policy=None) -> str:
        return f"{self.db_name}-{self._get_retention_policy_name(retention_policy)}-ilm"

    def _get_template_name(self, retention_policy=None) -> str:
        return f"{self._get_stream_name(retention_policy)}-template"

    def _build_resource_metadata(self) -> dict[str, Any]:
        return {
            "description": self._RESOURCE_DESCRIPTION,
            self._RESOURCE_METADATA_KEY: {"database": self.db_name},
        }

    def _is_own_resource(self, resource: Mapping[str, Any]) -> bool:
        metadata = resource.get("_meta", {})
        return metadata.get(self._RESOURCE_METADATA_KEY) == {"database": self.db_name}

    def _is_not_found(self, exception: Exception) -> bool:
        return isinstance(exception, NotFoundError) or (
            isinstance(exception, ApiError)
            and getattr(exception, "status_code", None) == 404
        )

    def _is_resource_exists(self, exception: Exception) -> bool:
        if not isinstance(exception, ApiError):
            return False
        if getattr(exception, "status_code", None) != 400:
            return False
        body = self._response_body(exception)
        error = body.get("error", {}) if isinstance(body, Mapping) else {}
        if isinstance(error, Mapping):
            return error.get("type") == "resource_already_exists_exception"
        return error == "resource_already_exists_exception"

    def _response_body(self, response):
        return getattr(response, "body", response)

    def _duration_to_seconds(self, duration: str | None) -> int | None:
        if duration is None:
            return None
        if not isinstance(duration, str) or not self._DURATION_PATTERN.fullmatch(
            duration
        ):
            raise ValueError(f'Invalid duration "{duration}"')
        mapping = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
        return sum(
            int(value) * mapping[unit]
            for value, unit in self._DURATION_PART_PATTERN.findall(duration)
        )

    def _build_lifecycle_policy(self, duration: str | None = None) -> dict[str, Any]:
        duration_seconds = self._duration_to_seconds(duration)
        # Bound retention overshoot and backing-index size for long-lived policies.
        rollover_seconds = min(
            duration_seconds or self._DEFAULT_ROLLOVER_SECONDS,
            self._DEFAULT_ROLLOVER_SECONDS,
        )
        policy = {
            "_meta": self._build_resource_metadata(),
            "phases": {
                "hot": {
                    "actions": {
                        "rollover": {
                            "max_age": f"{rollover_seconds}s",
                            "max_primary_shard_size": self.options.get(
                                "rollover_max_primary_shard_size", "50gb"
                            ),
                        }
                    }
                }
            },
        }
        if duration_seconds:
            policy["phases"]["delete"] = {
                "min_age": f"{duration_seconds}s",
                "actions": {"delete": {}},
            }
        return policy

    def _put_lifecycle_policy(self, name: str, policy: Mapping[str, Any]) -> None:
        self.db.ilm.put_lifecycle(name=name, policy=policy)

    def _build_index_template_body(self, retention_policy=None) -> dict[str, Any]:
        stream_name = self._get_stream_name(retention_policy)
        return {
            "index_patterns": [stream_name],
            "data_stream": {},
            "priority": self._OPENWISP_INDEX_TEMPLATE_PRIORITY,
            "template": {
                "settings": {
                    "index.lifecycle.name": self._get_policy_name(retention_policy),
                },
                "mappings": {
                    "_meta": self._build_resource_metadata(),
                    "_source": {"excludes": ["indexed_fields"]},
                    "dynamic": True,
                    "dynamic_templates": [
                        {
                            "tag_values": {
                                "path_match": "tags.*",
                                "mapping": {
                                    "type": "keyword",
                                    "ignore_above": 2048,
                                },
                            }
                        },
                        {
                            "keyword_fields": {
                                "path_match": "indexed_fields.keyword.*",
                                "mapping": {
                                    "type": "keyword",
                                    "ignore_above": 8192,
                                },
                            }
                        },
                        {
                            "numeric_fields": {
                                "path_match": "indexed_fields.numeric.*",
                                "mapping": {
                                    "type": "double",
                                },
                            }
                        },
                        {
                            "boolean_fields": {
                                "path_match": "indexed_fields.boolean.*",
                                "mapping": {
                                    "type": "boolean",
                                },
                            }
                        },
                    ],
                    "properties": {
                        "@timestamp": {"type": "date"},
                        "measurement": {"type": "keyword"},
                        "openwisp_write_sequence": {
                            "type": "long",
                        },
                        "tags": {"type": "object", "dynamic": True},
                        # Preserve values in _source and index type-stable copies.
                        "fields": {"type": "object", "enabled": False},
                        "indexed_fields": {"type": "object", "dynamic": True},
                    },
                },
            },
            "_meta": self._build_resource_metadata(),
        }

    def _put_index_template(self, retention_policy=None) -> None:
        name = self._get_template_name(retention_policy)
        body = self._build_index_template_body(retention_policy)
        self.db.indices.put_index_template(name=name, **body)

    def _data_stream_exists(self, name: str) -> bool:
        try:
            self.db.indices.get_data_stream(name=name)
        except Exception as exception:
            if self._is_not_found(exception):
                return False
            raise
        return True

    def _ensure_data_stream_resources(
        self, retention_policy=None, duration: str | None = None
    ) -> None:
        stream_name = self._get_stream_name(retention_policy)
        self._put_lifecycle_policy(
            self._get_policy_name(retention_policy),
            self._build_lifecycle_policy(duration),
        )
        self._put_index_template(retention_policy)
        if not self._data_stream_exists(stream_name):
            try:
                self.db.indices.create_data_stream(name=stream_name)
            except Exception as exception:
                if not self._is_resource_exists(exception):
                    raise
                if not self._data_stream_exists(stream_name):
                    raise

    @retry
    def create_database(self) -> None:
        self._ensure_data_stream_resources()
        logger.debug('Created Elasticsearch data stream "%s"', self.db_name)

    @retry
    def drop_database(self) -> None:
        for stream_name in self._get_data_stream_names():
            try:
                self.db.indices.delete_data_stream(name=stream_name)
            except Exception as exception:
                if not self._is_not_found(exception):
                    raise
        self._delete_indices()
        self._delete_index_templates()
        self._delete_lifecycle_policies()
        logger.debug('Dropped Elasticsearch data streams for "%s"', self.db_name)

    def _get_data_stream_names(self) -> list[str]:
        try:
            response = self.db.indices.get_data_stream(name=f"{self.db_name}*")
        except Exception as exception:
            if self._is_not_found(exception):
                return []
            raise
        response = self._response_body(response)
        return [
            stream["name"]
            for stream in response.get("data_streams", [])
            if self._is_own_resource(stream)
        ]

    def _get_index_names(self) -> list[str]:
        try:
            response = self.db.indices.get(
                index=f"{self.db_name}*",
                expand_wildcards="open,closed",
            )
        except Exception as exception:
            if self._is_not_found(exception):
                return []
            raise
        response = self._response_body(response)
        return [
            index_name
            for index_name, index in response.items()
            if self._is_own_resource(index.get("mappings", {}))
        ]

    def _delete_indices(self) -> None:
        for index_name in self._get_index_names():
            try:
                self.db.indices.delete(index=index_name)
            except Exception as exception:
                if not self._is_not_found(exception):
                    raise

    def _delete_index_templates(self) -> None:
        for template_name in self._get_index_template_names():
            try:
                self.db.indices.delete_index_template(name=template_name)
            except Exception as exception:
                if not self._is_not_found(exception):
                    raise

    def _get_index_templates(self) -> dict[str, Any]:
        try:
            response = self.db.indices.get_index_template(name=f"{self.db_name}*")
        except Exception as exception:
            if self._is_not_found(exception):
                return {}
            raise
        response = self._response_body(response)
        return {
            item["name"]: item["index_template"]
            for item in response.get("index_templates", [])
            if self._is_own_resource(item["index_template"])
        }

    def _get_index_template_names(self) -> list[str]:
        return list(self._get_index_templates())

    def _delete_lifecycle_policies(self) -> None:
        for policy_name in self._get_lifecycle_policy_names():
            try:
                self.db.ilm.delete_lifecycle(name=policy_name)
            except Exception as exception:
                if not self._is_not_found(exception):
                    raise

    def _get_lifecycle_policies(self) -> dict[str, Any]:
        pattern = f"{self.db_name}-*-ilm"
        try:
            response = self.db.ilm.get_lifecycle(name=pattern)
        except Exception as exception:
            if self._is_not_found(exception):
                return {}
            raise
        response = self._response_body(response)
        return {
            name: policy
            for name, policy in response.items()
            if name.startswith(f"{self.db_name}-")
            and name.endswith("-ilm")
            and self._is_own_resource(policy.get("policy", {}))
        }

    def _get_lifecycle_policy_names(self) -> list[str]:
        return list(self._get_lifecycle_policies())

    def create_or_alter_retention_policy(self, name: str, duration: str) -> None:
        self._get_stream_name(name)
        self._duration_to_seconds(duration)
        self._create_or_alter_retention_policy(name, duration)

    @retry
    def _create_or_alter_retention_policy(self, name: str, duration: str) -> None:
        self._ensure_data_stream_resources(retention_policy=name, duration=duration)
        logger.debug(
            'Created/updated Elasticsearch retention policy "%s" with duration %s',
            name,
            duration,
        )

    @retry
    def get_list_retention_policies(self) -> list[TimeseriesPoint]:
        """Return ES ILM policies in an InfluxDB-compatible shape."""
        policies = []
        prefix = f"{self.db_name}-"
        suffix = "-ilm"
        for policy_name, policy in self._get_lifecycle_policies().items():
            retention_policy = policy_name.removeprefix(prefix).removesuffix(suffix)
            phases = policy.get("policy", {}).get("phases", {})
            duration = "0s"
            if "delete" in phases:
                duration = phases["delete"].get("min_age", duration)
            policies.append(
                {
                    "name": retention_policy,
                    "default": retention_policy == "autogen",
                    "duration": duration,
                    "replication": 1,
                }
            )
        return sorted(policies, key=lambda item: (not item["default"], item["name"]))

    def _get_timezone(self, timezone_name=None):
        if not timezone_name:
            return timezone.utc
        try:
            return ZoneInfo(str(timezone_name))
        except Exception:
            return timezone.utc

    def _parse_timestamp(self, timestamp):
        if isinstance(timestamp, datetime):
            return timestamp
        if not isinstance(timestamp, str):
            return None
        parsed = parse_datetime(timestamp)
        if parsed is not None:
            return parsed
        if "T" not in timestamp and " " in timestamp:
            timestamp = timestamp.replace(" ", "T", 1)
            parsed = parse_datetime(timestamp)
            if parsed is not None:
                return parsed
        return None

    def _serialize_timestamp(self, timestamp, timezone_name=None):
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=self._get_timezone(timezone_name))
        timestamp = timestamp.astimezone(timezone.utc)
        return timestamp.isoformat().replace("+00:00", "Z")

    def _get_timestamp(self, timestamp=None, timezone_name=None) -> str:
        if timestamp is None:
            timestamp = now()
        parsed_timestamp = self._parse_timestamp(timestamp)
        if parsed_timestamp is not None:
            return self._serialize_timestamp(
                parsed_timestamp, timezone_name=timezone_name
            )
        return timestamp

    def _normalize_time(self, value, precision="s"):
        return _normalize_timestamp_value(value, precision=precision)

    def _clean_operator(self, op: str) -> str:
        if op not in self._OPERATORS:
            message = _(
                'Invalid operator "%(operator)s" passed.\n'
                "Valid operators are: %(operators)s"
            ) % {"operator": op, "operators": ", ".join(self._OPERATORS)}
            raise self.client_error(message)
        return op

    def _check_database_kwarg(self, database) -> None:
        if database and database != self.db_name:
            logger.warning(
                'Parameter "database" is ignored in Elasticsearch. '
                'Using data stream namespace "%s"',
                self.db_name,
            )

    @classmethod
    def _get_indexed_field_path(cls, field, field_type):
        return f"{cls._INDEXED_FIELD_PATHS[field_type]}.{field}"

    @staticmethod
    def _get_indexed_field_type(value):
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, (int, float)):
            return "numeric"
        if isinstance(value, str):
            return "keyword"

    def _build_indexed_fields(self, values):
        indexed_fields = {}
        for field, value in values.items():
            field_type = self._get_indexed_field_type(value)
            if field_type:
                indexed_fields.setdefault(field_type, {})[field] = value
        return indexed_fields

    def _build_document(self, name, values, **kwargs) -> dict[str, Any]:
        values = dict(values or {})
        return {
            "@timestamp": self._get_timestamp(kwargs.get("timestamp")),
            "measurement": name,
            "openwisp_write_sequence": next(self._write_sequence),
            "tags": dict(kwargs.get("tags") or {}),
            "fields": values,
            "indexed_fields": self._build_indexed_fields(values),
        }

    def _handle_write_exception(self, exception) -> None:
        logger.warning("Error writing to Elasticsearch: %s", exception)
        raise TimeseriesWriteException from exception

    def write(self, name: str, values: TimeseriesFields, **kwargs: Any) -> None:
        self._check_database_kwarg(kwargs.get("database"))
        retention_policy = kwargs.get("retention_policy")
        document = self._build_document(name, values, **kwargs)
        try:
            self.db.index(
                index=self._get_stream_name(retention_policy),
                id=kwargs.get("operation_id") or uuid4().hex,
                document=document,
                op_type="create",
                refresh=self.refresh,
            )
        except ConflictError:
            return
        except Exception as exception:
            self._handle_write_exception(exception)

    def batch_write(self, metric_data: Sequence[BatchWritePayload]) -> None:
        actions = []
        checked_databases = set()
        for data in metric_data:
            database = data.get("database")
            if database not in checked_databases:
                self._check_database_kwarg(database)
                checked_databases.add(database)
            retention_policy = data.get("retention_policy")
            actions.append(
                {
                    "_op_type": "create",
                    "_index": self._get_stream_name(retention_policy),
                    "_id": data.get("operation_id") or uuid4().hex,
                    "_source": self._build_document(
                        data.get("name"),
                        data.get("values"),
                        tags=data.get("tags"),
                        timestamp=data.get("timestamp"),
                    ),
                }
            )
        if not actions:
            return
        try:
            bulk(
                self.db,
                actions,
                refresh=self.refresh,
                ignore_status=(409,),
            )
        except Exception as exception:
            self._handle_write_exception(exception)

    def _empty_search_response(self) -> dict[str, Any]:
        return {"hits": {"total": {"value": 0}, "hits": []}}

    def _prepare_search_query(self, query, index=None):
        if not isinstance(query, Mapping):
            raise self.client_error("Elasticsearch queries must be dictionaries.")
        query = deepcopy(query)
        index = (
            index
            or query.pop("__index", None)
            or query.pop("index", None)
            or self._get_stream_name(query.pop("__retention_policy", None))
        )
        for key in list(query.keys()):
            if key.startswith("__openwisp_"):
                query.pop(key)
        return index, query

    @retry
    def query(
        self, query, precision: str | None = None, **kwargs: Any
    ) -> QueryResultSet:
        index, query = self._prepare_search_query(query, kwargs.get("index"))
        try:
            response = self.db.search(index=index, body=query)
        except Exception as exception:
            if self._is_not_found(exception):
                return QueryResultSet(
                    self._empty_search_response(), precision=precision
                )
            logger.warning("Error querying Elasticsearch: %s", exception)
            raise
        return QueryResultSet(self._response_body(response), precision=precision)

    @retry
    def _get_paginated_hits(self, query, should_stop=None):
        """Read stable hit pages until exhausted or a logical limit is complete."""
        index, query = self._prepare_search_query(query)
        page_size = int(query.get("size", self.options.get("read_size", 10000)))
        if page_size <= 0:
            return []
        query["size"] = page_size
        sort = list(query.get("sort") or [])
        # PIT keeps this shard-level tie-breaker stable across search_after pages.
        if not any(
            item == "_shard_doc" or isinstance(item, Mapping) and "_shard_doc" in item
            for item in sort
        ):
            sort.append({"_shard_doc": "asc"})
        query["sort"] = sort
        pit_id = None
        hits = []
        search_after = None
        try:
            response = self.db.open_point_in_time(
                index=index,
                keep_alive=self._PIT_KEEP_ALIVE,
            )
            pit_id = self._response_body(response)["id"]
            while True:
                body = deepcopy(query)
                body["pit"] = {
                    "id": pit_id,
                    "keep_alive": self._PIT_KEEP_ALIVE,
                }
                if search_after is not None:
                    body["search_after"] = search_after
                response = self._response_body(self.db.search(body=body))
                pit_id = response.get("pit_id", pit_id)
                page = self._get_hits(response)
                if not page:
                    break
                hits.extend(page)
                if should_stop and should_stop(hits):
                    break
                if len(page) < page_size:
                    break
                search_after = page[-1].get("sort")
                if search_after is None:
                    raise self.client_error(
                        "Elasticsearch paginated search response is missing sort values."
                    )
        except Exception as exception:
            if self._is_not_found(exception):
                return []
            logger.warning("Error querying Elasticsearch: %s", exception)
            raise
        finally:
            if pit_id is not None:
                try:
                    self.db.close_point_in_time(id=pit_id)
                except Exception as exception:
                    logger.warning(
                        "Error closing Elasticsearch point in time: %s", exception
                    )
        return hits

    @retry
    def _count_distinct_values(self, query, field_path) -> int:
        """Count unique values by paging a composite aggregation."""
        index, query = self._prepare_search_query(query)
        query["size"] = 0
        query["aggs"] = {
            "distinct": {
                "composite": {
                    "size": self._DISTINCT_PAGE_SIZE,
                    "sources": [{"value": {"terms": {"field": field_path}}}],
                }
            }
        }
        pit_id = None
        count = 0
        after_key = None
        try:
            response = self.db.open_point_in_time(
                index=index,
                keep_alive=self._PIT_KEEP_ALIVE,
            )
            pit_id = self._response_body(response)["id"]
            while True:
                body = deepcopy(query)
                body["pit"] = {
                    "id": pit_id,
                    "keep_alive": self._PIT_KEEP_ALIVE,
                }
                if after_key is not None:
                    body["aggs"]["distinct"]["composite"]["after"] = after_key
                response = self._response_body(self.db.search(body=body))
                pit_id = response.get("pit_id", pit_id)
                aggregation = response.get("aggregations", {}).get("distinct", {})
                buckets = aggregation.get("buckets", [])
                count += len(buckets)
                after_key = aggregation.get("after_key")
                if after_key is None or len(buckets) < self._DISTINCT_PAGE_SIZE:
                    break
        except Exception as exception:
            if self._is_not_found(exception):
                return 0
            logger.warning("Error querying Elasticsearch: %s", exception)
            raise
        finally:
            if pit_id is not None:
                try:
                    self.db.close_point_in_time(id=pit_id)
                except Exception as exception:
                    logger.warning(
                        "Error closing Elasticsearch point in time: %s", exception
                    )
        return count

    def _normalize_fields(self, fields, extra_fields=None):
        if isinstance(fields, str):
            fields = [fields]
        else:
            fields = list(fields)
        if extra_fields and extra_fields != "*":
            if isinstance(extra_fields, str):
                extra_fields = [extra_fields]
            fields.extend(extra_fields)
        elif extra_fields == "*":
            fields = ["*"]
        return fields

    def _build_measurement_filter(self, key):
        measurements = [item.strip() for item in key.split(",") if item.strip()]
        if not measurements:
            return None
        if len(measurements) == 1:
            return {"term": {"measurement": measurements[0]}}
        return {"terms": {"measurement": measurements}}

    def _build_field_filter(self, field, op, value):
        op = self._clean_operator(op)
        field_type = self._get_indexed_field_type(value) or "keyword"
        field_name = self._get_indexed_field_path(field, field_type)
        if op == "=":
            return {"term": {field_name: value}}
        if op == "!=":
            return {"bool": {"must_not": [{"term": {field_name: value}}]}}
        range_operator = {">": "gt", ">=": "gte", "<": "lt", "<=": "lte"}[op]
        return {"range": {field_name: {range_operator: value}}}

    def _build_field_exists_filter(self, fields):
        if not fields or fields == ["*"]:
            return None
        fields = [field for field in fields if field != "*"]
        if not fields:
            return None
        filters = []
        for field in fields:
            keyword_path = self._get_indexed_field_path(field, "keyword")
            type_filters = [
                {"exists": {"field": self._get_indexed_field_path(field, field_type)}}
                for field_type in self._INDEXED_FIELD_PATHS
            ]
            type_filters.append({"term": {"_ignored": keyword_path}})
            filters.append(
                {
                    "bool": {
                        "should": type_filters,
                        "minimum_should_match": 1,
                    }
                }
            )
        if len(filters) == 1:
            return filters[0]
        return {"bool": {"should": filters, "minimum_should_match": 1}}

    def _add_filter(self, query, filter_query):
        if not filter_query:
            return query
        if query == {"match_all": {}}:
            return {"bool": {"filter": [filter_query]}}
        query = deepcopy(query)
        query.setdefault("bool", {}).setdefault("filter", []).append(filter_query)
        return query

    def _get_read_exists_fields(self, fields, where):
        if fields == ["*"]:
            exists_fields = []
        else:
            exists_fields = list(fields)
        exists_fields.extend(condition[0] for condition in where)
        if not exists_fields:
            return ["*"]
        return list(dict.fromkeys(exists_fields))

    def _matches_where(self, point, where):
        for field, op, value in where:
            op = self._clean_operator(op)
            point_value = point.get(field)
            if point_value is None:
                return False
            if op == "=" and point_value != value:
                return False
            if op == "!=" and point_value == value:
                return False
            if op == ">" and not point_value > value:
                return False
            if op == ">=" and not point_value >= value:
                return False
            if op == "<" and not point_value < value:
                return False
            if op == "<=" and not point_value <= value:
                return False
        return True

    def _filter_points(self, points, where):
        if not where:
            return points
        return [point for point in points if self._matches_where(point, where)]

    def _build_base_query(
        self,
        key: str | None = None,
        tags: TimeseriesTags | None = None,
        since=None,
        where: Sequence[Sequence[Any]] | None = None,
        timestamp=None,
    ) -> dict[str, Any]:
        filters = []
        measurement_filter = self._build_measurement_filter(key) if key else None
        if measurement_filter:
            filters.append(measurement_filter)
        if since:
            filters.append(
                {"range": {"@timestamp": {"gte": self._get_timestamp(since)}}}
            )
        if timestamp is not None:
            serialized_timestamp = self._get_timestamp(timestamp)
            filters.append(
                {
                    "range": {
                        "@timestamp": {
                            "gte": serialized_timestamp,
                            "lte": serialized_timestamp,
                        }
                    }
                }
            )
        if tags:
            for tag_key, tag_value in tags.items():
                filters.append({"term": {f"tags.{tag_key}": tag_value}})
        if where:
            for field, op, value in where:
                filters.append(self._build_field_filter(field, op, value))
        if not filters:
            return {"match_all": {}}
        return {"bool": {"filter": filters}}

    def _document_to_point(
        self,
        document: Mapping[str, Any],
        fields: Sequence[str] | None = None,
        precision: str | None = "s",
        include_tags: bool = True,
    ) -> TimeseriesPoint:
        timestamp = document.get("@timestamp")
        point = {"time": self._normalize_time(timestamp, precision=precision)}
        if include_tags:
            point.update(document.get("tags") or {})
        values = document.get("fields") or {}
        if not fields or fields == ["*"]:
            point.update(values)
        else:
            tags = document.get("tags") or {}
            for field in fields:
                if field in values:
                    point[field] = values[field]
                elif field in tags:
                    point[field] = tags[field]
        point.update(
            {
                "__openwisp_time_key": timestamp,
                "__openwisp_measurement_key": document.get("measurement"),
                "__openwisp_tags_key": tuple(
                    sorted((document.get("tags") or {}).items())
                ),
            }
        )
        return point

    def _get_hits(self, response) -> list[Mapping[str, Any]]:
        if isinstance(response, QueryResultSet):
            response = response.response
        return response.get("hits", {}).get("hits", [])

    def _count_distinct_read(
        self,
        key,
        tags,
        field,
        since=None,
        where=None,
        retention_policy=None,
        limit=None,
        precision="s",
    ) -> list[TimeseriesPoint]:
        value = self._count_distinct_values(
            {
                "query": self._build_base_query(
                    key=key, tags=tags, since=since, where=where
                ),
                "__retention_policy": retention_policy,
            },
            self._get_indexed_field_path(field, "keyword"),
        )
        points = [{"count": value, "time": None}]
        return points[: int(limit)] if limit else points

    def read(
        self,
        key: str,
        fields: FieldSelection,
        tags: TimeseriesTags | None,
        **kwargs: Any,
    ) -> list[TimeseriesPoint]:
        distinct_fields = kwargs.get("distinct_fields", [])
        count_fields = kwargs.get("count_fields", [])
        where = kwargs.get("where", [])
        supports_count_distinct = (
            len(distinct_fields) == 1
            and len(count_fields) == 1
            and distinct_fields[0] == count_fields[0]
        )
        if (distinct_fields or count_fields) and not supports_count_distinct:
            raise NotImplementedError(
                "Elasticsearch read() currently supports only single-field "
                "COUNT(DISTINCT(field)) queries."
            )
        retention_policy = kwargs.get("retention_policy")
        limit = kwargs.get("limit")
        precision = kwargs.get("precision", "s")
        if supports_count_distinct:
            return self._count_distinct_read(
                key=key,
                tags=tags,
                field=distinct_fields[0],
                since=kwargs.get("since"),
                where=where,
                retention_policy=retention_policy,
                limit=limit,
                precision=precision,
            )
        fields = self._normalize_fields(fields, kwargs.get("extra_fields"))
        order = kwargs.get("order") or kwargs.get("order_by")
        if order in (None, "time"):
            sort = [
                {"@timestamp": {"order": "asc"}},
                {"openwisp_write_sequence": {"order": "asc", "unmapped_type": "long"}},
            ]
        elif order == "-time":
            sort = [
                {"@timestamp": {"order": "desc"}},
                {"openwisp_write_sequence": {"order": "asc", "unmapped_type": "long"}},
            ]
        else:
            message = _(
                'Invalid order "%(order)s" passed.\n'
                'You may pass "time" / "-time" to get result sorted '
                "in ascending /descending order respectively."
            ) % {"order": order}
            raise self.client_error(message)
        query = {
            "query": self._add_filter(
                self._build_base_query(
                    key=key,
                    tags=tags,
                    since=kwargs.get("since"),
                ),
                self._build_field_exists_filter(
                    self._get_read_exists_fields(fields, where)
                ),
            ),
            "sort": sort,
            "__retention_policy": retention_policy,
            "size": int(self.options.get("read_size", 10000)),
        }
        where_fields = [condition[0] for condition in where]
        projection_fields = fields
        filter_only_fields = set()
        if fields != ["*"]:
            projection_fields = list(dict.fromkeys([*fields, *where_fields]))
            filter_only_fields = set(where_fields) - set(fields)

        def get_filtered_points(hits):
            points = [
                self._document_to_point(
                    hit.get("_source", {}),
                    fields=projection_fields,
                    precision=precision,
                    include_tags=False,
                )
                for hit in hits
            ]
            points = self._merge_points_by_time(points, preserve_time_key=True)
            return self._filter_points(points, where)

        logical_limit = int(limit) if limit else None

        def has_complete_limit(hits):
            if not logical_limit or logical_limit < 0:
                return False
            points = get_filtered_points(hits)
            if len(points) < logical_limit:
                return False
            boundary_time = points[logical_limit - 1]["__openwisp_time_key"]
            last_hit_time = hits[-1].get("_source", {}).get("@timestamp")
            return boundary_time != last_hit_time

        hits = self._get_paginated_hits(
            query,
            should_stop=has_complete_limit if logical_limit else None,
        )
        points = get_filtered_points(hits)
        hidden_fields = {*filter_only_fields, "__openwisp_time_key"}
        points = [
            {
                field: value
                for field, value in point.items()
                if field not in hidden_fields
            }
            for point in points
        ]
        return points[: int(limit)] if limit else points

    def _format_query_mapping(self, value, params):
        if isinstance(value, str):
            return value.format_map(_SafeFormatDict(params))
        if isinstance(value, Mapping):
            return {
                key: self._format_query_mapping(item, params)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self._format_query_mapping(item, params) for item in value]
        return value

    def _is_openwisp_query(self, query, query_type=None) -> bool:
        if not isinstance(query, Mapping):
            return False
        current_type = query.get("__openwisp_query_type")
        if query_type is None:
            return bool(current_type)
        return current_type == query_type

    def _build_tag_filter(self, field, value):
        if value in (None, ""):
            return None
        tag_field = f"tags.{field}"
        if isinstance(value, (list, tuple)):
            values = [str(item) for item in value]
            if not values:
                return None
            return {"terms": {tag_field: values}}
        return {"term": {tag_field: str(value)}}

    def _build_chart_base_query(self, params, timezone_name=None, end_date=True):
        filters = []
        measurement_filter = self._build_measurement_filter(params.get("key"))
        if measurement_filter:
            filters.append(measurement_filter)
        time_filter = {}
        if params.get("time"):
            time_filter["gte"] = self._get_timestamp(
                params["time"], timezone_name=timezone_name
            )
        if end_date and params.get("end_date"):
            time_filter["lte"] = self._get_timestamp(
                params["end_date"], timezone_name=timezone_name
            )
        if time_filter:
            filters.append({"range": {"@timestamp": time_filter}})
        for field in self._CHART_FILTERS:
            tag_filter = self._build_tag_filter(field, params.get(field))
            if tag_filter:
                filters.append(tag_filter)
        if not filters:
            return {"match_all": {}}
        return {"bool": {"filter": filters}}

    def _format_chart_metrics(self, query, params, fields=None):
        format_params = {**params}
        dynamic_metric = query.get("dynamic_metric")
        if dynamic_metric is not None:
            if not fields:
                return []
            dynamic_metric = self._format_query_mapping(dynamic_metric, format_params)
            return [
                {**dynamic_metric, "name": field, "field": field} for field in fields
            ]
        metrics = self._format_query_mapping(query.get("metrics", []), format_params)
        if fields:
            selected_fields = set(fields)
            metrics = [
                metric
                for metric in metrics
                if metric.get("field") in selected_fields
                or metric.get("name") in selected_fields
            ]
        return [metric for metric in metrics if metric.get("field")]

    def _build_metric_aggregation(self, metric):
        aggregation = metric.get("agg", "avg")
        field = self._get_metric_field_path(metric)
        if aggregation == "sum":
            metric_aggregation = {"sum": {"field": field}}
        elif aggregation == "cardinality":
            metric_aggregation = {
                "cardinality": {
                    "field": field,
                    "precision_threshold": self._CARDINALITY_PRECISION,
                }
            }
        elif aggregation == "mode":
            metric_aggregation = {"terms": {"field": field, "size": 1}}
        elif aggregation == "last":
            metric_aggregation = {
                "top_metrics": {
                    "metrics": {"field": field},
                    "sort": {"@timestamp": "desc"},
                }
            }
        else:
            metric_aggregation = {"avg": {"field": field}}
        return {
            "filter": {"exists": {"field": field}},
            "aggs": {"value": metric_aggregation},
        }

    @classmethod
    def _get_metric_field_path(cls, metric):
        field_type = "keyword" if metric.get("agg") == "cardinality" else "numeric"
        return cls._get_indexed_field_path(metric["field"], field_type)

    def _build_metric_aggregations(self, metrics):
        return {
            metric["name"]: self._build_metric_aggregation(metric) for metric in metrics
        }

    def _build_chart_query(
        self,
        query,
        params,
        time,
        group_map,
        summary=False,
        timezone=None,
        fields=None,
    ):
        metrics = self._format_chart_metrics(query, params, fields=fields)
        body = {
            "size": 0,
            "query": self._build_chart_base_query(
                params,
                timezone_name=timezone,
                end_date=query.get("end_date", True),
            ),
            "__index": self._get_stream_name(params.get("retention_policy")),
            "__openwisp_query_type": "chart",
            "__openwisp_metrics": metrics,
            "__openwisp_summary": summary,
            "__openwisp_aggregate": True,
        }
        metric_aggs = self._build_metric_aggregations(metrics)
        if summary:
            body["aggs"] = metric_aggs
            return body
        histogram = {
            "field": "@timestamp",
            "fixed_interval": self._normalize_chart_window(time, group_map),
            "min_doc_count": 0,
        }
        if params.get("time"):
            histogram["extended_bounds"] = {
                "min": self._get_timestamp(params["time"], timezone_name=timezone),
                "max": self._get_timestamp(
                    params.get("end_date") or now(), timezone_name=timezone
                ),
            }
        if timezone:
            histogram["time_zone"] = timezone
        body["aggs"] = {
            "timeseries": {
                "date_histogram": histogram,
                "aggs": metric_aggs,
            }
        }
        return body

    def _build_grouped_chart_query(
        self,
        query,
        params,
        time,
        group_map,
        summary=False,
        timezone=None,
    ):
        metric = self._format_query_mapping(query["metric"], params)
        group_by = query["group_by"]
        excluded_params = {group_by}
        if not query.get("object_scope", True):
            excluded_params.update(("content_type", "object_id"))
        base_params = {
            key: value for key, value in params.items() if key not in excluded_params
        }
        body = {
            "size": 0,
            "query": self._build_chart_base_query(base_params, timezone_name=timezone),
            "__index": self._get_stream_name(params.get("retention_policy")),
            "__openwisp_query_type": "grouped_chart",
            "__openwisp_metric": metric,
            "__openwisp_group_by": group_by,
            "__openwisp_summary": summary,
            "__openwisp_cumulative": bool(query.get("cumulative")),
            "__openwisp_fill": query.get("fill"),
            "__openwisp_aggregate": True,
        }
        group_aggs = {
            "groups": {
                "terms": {
                    "field": f"tags.{group_by}",
                    "size": int(self.options.get("terms_size", 1000)),
                },
                "aggs": {"value": self._build_metric_aggregation(metric)},
            }
        }
        if summary:
            body["aggs"] = group_aggs
            return body
        histogram = {
            "field": "@timestamp",
            "fixed_interval": self._normalize_chart_window(time, group_map),
            "min_doc_count": 0,
        }
        if timezone:
            histogram["time_zone"] = timezone
        body["aggs"] = {
            "timeseries": {
                "date_histogram": histogram,
                "aggs": group_aggs,
            }
        }
        return body

    def _normalize_raw_chart_fields(self, query, params, fields=None):
        if fields:
            return list(fields)
        configured_fields = query.get("fields")
        if configured_fields:
            return list(self._format_query_mapping(configured_fields, params))
        field = self._format_query_mapping(query.get("field"), params)
        if not field or field == "{fields}":
            return ["*"]
        return [field]

    def _build_raw_chart_query(self, query, params, fields=None, timezone=None):
        selected_fields = self._normalize_raw_chart_fields(query, params, fields)
        return {
            "size": int(self.options.get("read_size", 10000)),
            "query": self._add_filter(
                self._build_chart_base_query(params, timezone_name=timezone),
                self._build_field_exists_filter(selected_fields),
            ),
            "sort": [{"@timestamp": {"order": "asc"}}],
            "__index": self._get_stream_name(params.get("retention_policy")),
            "__openwisp_query_type": "raw_chart",
            "__openwisp_fields": selected_fields,
            "__openwisp_aggregate": False,
        }

    def validate_query(self, query) -> bool:
        if not isinstance(query, Mapping):
            raise ValidationError(
                {"configuration": _("Elasticsearch queries must be dictionaries.")}
            )
        if not query:
            return False
        if self._is_openwisp_query(query):
            return bool(query.get("aggregate", query.get("__openwisp_aggregate", True)))
        if query.get("aggs") or query.get("aggregations"):
            raise ValidationError(
                {
                    "configuration": _(
                        "Native Elasticsearch aggregations are not supported in "
                        "chart queries. Use an OpenWISP Elasticsearch chart query "
                        "descriptor instead."
                    )
                }
            )
        validation_query = query.get("query", {"match_all": {}})
        try:
            response = self.db.indices.validate_query(
                index=self._get_stream_name(),
                body={"query": validation_query},
                explain=True,
            )
        except Exception as exception:
            if not self._is_not_found(exception):
                raise
            return False
        response = self._response_body(response)
        if not response.get("valid", False):
            message = response.get("error") or _("Invalid Elasticsearch query")
            raise ValidationError({"configuration": message})
        return False

    def get_query(
        self,
        chart_type: str,
        params: ChartQueryParams,
        time: Any,
        group_map: Mapping[Any, str],
        summary: bool = False,
        fields: Sequence[str] | None = None,
        query: Mapping[str, Any] | None = None,
        timezone: str | None = settings.TIME_ZONE,
    ) -> Mapping[str, Any]:
        if not query:
            query = self.get_default_chart_query(
                has_object_scope=bool(params.get("object_id"))
            )
        if self._is_openwisp_query(query, "chart"):
            return self._build_chart_query(
                query,
                params,
                time,
                group_map,
                summary=summary,
                timezone=timezone,
                fields=fields,
            )
        if self._is_openwisp_query(query, "grouped_chart"):
            return self._build_grouped_chart_query(
                query,
                params,
                time,
                group_map,
                summary=summary,
                timezone=timezone,
            )
        if self._is_openwisp_query(query, "raw_chart"):
            return self._build_raw_chart_query(
                query, params, fields=fields, timezone=timezone
            )
        format_params = {
            **params,
            "time": params.get("time", time),
            "window": group_map.get(time, time),
            "timezone": timezone or "UTC",
            "fields": ",".join(fields or []),
        }
        formatted_query = self._format_query_mapping(query, format_params)
        if "index" not in formatted_query and "__index" not in formatted_query:
            formatted_query["__index"] = self._get_stream_name(
                params.get("retention_policy")
            )
        return formatted_query

    def _get_top_fields(
        self,
        query: str | None,
        params: ChartQueryParams,
        chart_type: str,
        group_map: Mapping[Any, str],
        number: int,
        time: Any,
        timezone: str | None = settings.TIME_ZONE,
    ) -> list[str]:
        if number <= 0:
            return []
        # Dynamic field names must be discovered and summed without fetching a
        # capped set of matching documents into the application.
        search = {
            "size": 0,
            "query": self._build_chart_base_query(params, timezone_name=timezone),
            "aggs": {
                "top_fields": {
                    "scripted_metric": {
                        "init_script": "state.totals = [:]",
                        "map_script": (
                            "def values = params['_source']['fields']; "
                            "if (values == null) return; "
                            "for (def entry : values.entrySet()) { "
                            "def value = entry.getValue(); "
                            "if (value instanceof Number) { "
                            "def name = entry.getKey(); "
                            "state.totals[name] = state.totals.containsKey(name) "
                            "? state.totals[name] + value : value; "
                            "} "
                            "}"
                        ),
                        "combine_script": "return state.totals",
                        "reduce_script": (
                            "Map totals = [:]; "
                            "for (def shard : states) { "
                            "if (shard == null) continue; "
                            "for (def entry : shard.entrySet()) { "
                            "def name = entry.getKey(); "
                            "totals[name] = totals.containsKey(name) "
                            "? totals[name] + entry.getValue() : entry.getValue(); "
                            "} "
                            "} "
                            "return totals"
                        ),
                    }
                }
            },
            "__index": self._get_stream_name(params.get("retention_policy")),
        }
        response = self.query(search, precision="s")
        totals = (
            response.get("aggregations", {}).get("top_fields", {}).get("value") or {}
        )
        totals = {
            field: value
            for field, value in totals.items()
            if not isinstance(value, bool) and isinstance(value, (int, float))
        }
        sorted_fields = sorted(totals.items(), key=lambda item: (-item[1], item[0]))
        return [field for field, _value in sorted_fields[:number]]

    def _round_chart_value(self, value):
        if value >= 0:
            return float(int(value + 0.5))
        return float(int(value - 0.5))

    def _extract_chart_metric_value(self, aggregation, metric):
        metric_aggregation = aggregation.get(metric["name"], {})
        if "doc_count" in metric_aggregation:
            if metric_aggregation["doc_count"] == 0:
                return None
            metric_aggregation = metric_aggregation.get("value", {})
        if metric.get("agg") == "mode":
            buckets = metric_aggregation.get("buckets", [])
            value = buckets[0]["key"] if buckets else None
        elif metric.get("agg") == "last":
            rows = metric_aggregation.get("top", [])
            value = (
                rows[0].get("metrics", {}).get(self._get_metric_field_path(metric))
                if rows
                else None
            )
        else:
            value = metric_aggregation.get("value")
        if value is None:
            return None
        if metric.get("scale") is not None:
            value *= metric["scale"]
        if metric.get("round"):
            value = self._round_chart_value(value)
        return value

    def _build_chart_point(self, aggregation, metrics, time_value=None):
        point = {"time": time_value}
        for metric in metrics:
            point[metric["name"]] = self._extract_chart_metric_value(
                aggregation, metric
            )
        return point

    @staticmethod
    def _has_chart_values(points, metrics):
        metric_names = [metric["name"] for metric in metrics]
        return any(
            point.get(metric_name) is not None
            for point in points
            for metric_name in metric_names
        )

    @staticmethod
    def _fill_empty_cardinality_values(points, metrics):
        # COUNT(DISTINCT) reports 0 for empty buckets on the InfluxDB backends.
        # This is only applied to charts which have data, so that charts without
        # any data are left empty instead of being rendered as a flat zero line.
        metric_names = [
            metric["name"] for metric in metrics if metric.get("agg") == "cardinality"
        ]
        for point in points:
            for metric_name in metric_names:
                if point.get(metric_name) is None:
                    point[metric_name] = 0
        return points

    def _format_histogram_time(self, bucket, precision):
        if "key" not in bucket:
            return None
        value = datetime.fromtimestamp(bucket["key"] / 1000, tz=timezone.utc)
        return self._normalize_time(value, precision=precision)

    def _get_chart_points(self, response, query, precision="s"):
        metrics = query.get("__openwisp_metrics", [])
        aggregations = response.get("aggregations", {})
        if query.get("__openwisp_summary"):
            point = self._build_chart_point(aggregations, metrics)
            if not self._has_chart_values([point], metrics):
                return []
            return self._fill_empty_cardinality_values([point], metrics)
        buckets = aggregations.get("timeseries", {}).get("buckets", [])
        points = [
            self._build_chart_point(
                bucket,
                metrics,
                time_value=self._format_histogram_time(bucket, precision),
            )
            for bucket in buckets
        ]
        if not self._has_chart_values(points, metrics):
            return []
        return self._fill_empty_cardinality_values(points, metrics)

    def _extract_grouped_chart_value(self, bucket, metric):
        return self._extract_chart_metric_value(
            {metric["name"]: bucket.get("value", {})}, metric
        )

    def _warn_if_grouped_chart_truncated(self, aggregations, query):
        if query.get("__openwisp_summary"):
            groups = (aggregations.get("groups", {}),)
        else:
            groups = (
                bucket.get("groups", {})
                for bucket in aggregations.get("timeseries", {}).get("buckets", [])
            )
        omitted_documents = sum(
            group.get("sum_other_doc_count", 0) or 0 for group in groups
        )
        if omitted_documents:
            logger.warning(
                'Elasticsearch grouped chart for tag "%s" omitted groups '
                "containing %d document(s) because the terms_size limit (%d) "
                "was reached.",
                query.get("__openwisp_group_by"),
                omitted_documents,
                int(self.options.get("terms_size", 1000)),
            )

    def _get_grouped_chart_points(self, response, query, precision="s"):
        aggregations = response.get("aggregations", {})
        self._warn_if_grouped_chart_truncated(aggregations, query)
        metric = query["__openwisp_metric"]
        if query.get("__openwisp_summary"):
            point = {"time": None}
            for bucket in aggregations.get("groups", {}).get("buckets", []):
                point[bucket["key"]] = self._extract_grouped_chart_value(bucket, metric)
            return [point]
        totals = {}
        previous_values = {}
        fill_previous = query.get("__openwisp_fill") == "previous"
        points = []
        for bucket in aggregations.get("timeseries", {}).get("buckets", []):
            point = {"time": self._format_histogram_time(bucket, precision)}
            for group_bucket in bucket.get("groups", {}).get("buckets", []):
                value = self._extract_grouped_chart_value(group_bucket, metric)
                key = group_bucket["key"]
                if query.get("__openwisp_cumulative"):
                    totals[key] = totals.get(key, 0) + (value or 0)
                    value = totals[key]
                point[key] = value
            if fill_previous:
                for key, value in point.items():
                    if key != "time" and value is not None:
                        previous_values[key] = value
                for key, value in previous_values.items():
                    if point.get(key) is None:
                        point[key] = value
            if len(point) > 1:
                points.append(point)
        return points

    def _merge_points_by_time(self, points, preserve_time_key=False):
        merged = {}
        order = []
        for point in points:
            time_key = point.get("__openwisp_time_key", point.get("time"))
            series_key = (
                time_key,
                point.get("__openwisp_measurement_key"),
                point.get("__openwisp_tags_key"),
            )
            if series_key not in merged:
                merged[series_key] = {"time": point.get("time")}
                if preserve_time_key:
                    merged[series_key]["__openwisp_time_key"] = time_key
                order.append(series_key)
            merged[series_key].update(
                {
                    key: value
                    for key, value in point.items()
                    if key != "time" and key not in _POINT_IDENTITY_FIELDS
                }
            )
        return [merged[series_key] for series_key in order]

    @staticmethod
    def _backfill_raw_chart_fields(points, fields):
        if not fields:
            return points
        expected_fields = [field for field in fields if field != "*"]
        if "*" in fields:
            expected_fields.extend(
                field
                for point in points
                for field in point
                if field != "time" and field not in expected_fields
            )
        for point in points:
            for field in expected_fields:
                point.setdefault(field, None)
        return points

    def get_list_query(
        self, query: Mapping[str, Any], precision: str = "s"
    ) -> list[TimeseriesPoint]:
        if (
            isinstance(query, Mapping)
            and query.get("__openwisp_query_type") == "device_data"
        ):
            return self.read(
                key=query["measurement"],
                fields="data",
                tags={"pk": query["pk"]},
                retention_policy=query["retention_policy"],
                limit=1,
                order="-time",
                precision=precision,
            )
        if self._is_openwisp_query(query, "chart"):
            response = self.query(query, precision=precision)
            return self._get_chart_points(response, query, precision=precision)
        if self._is_openwisp_query(query, "grouped_chart"):
            response = self.query(query, precision=precision)
            return self._get_grouped_chart_points(response, query, precision=precision)
        if self._is_openwisp_query(query, "raw_chart"):
            hits = self._get_paginated_hits(query)
        else:
            response = self.query(query, precision=precision)
            hits = self._get_hits(response)
        fields = query.get("__openwisp_fields") if isinstance(query, Mapping) else None
        points = [
            self._document_to_point(
                hit.get("_source", {}),
                fields=fields,
                precision=precision,
                include_tags=False,
            )
            for hit in hits
        ]
        points = self._merge_points_by_time(points)
        if self._is_openwisp_query(query, "raw_chart"):
            return self._backfill_raw_chart_fields(points, fields)
        return points

    def get_device_data_query(
        self,
        retention_policy: str,
        measurement: str,
        pk: str,
    ) -> Mapping[str, str]:
        return {
            "__openwisp_query_type": "device_data",
            "retention_policy": retention_policy,
            "measurement": measurement,
            "pk": str(pk),
        }

    @retry
    def _delete_by_query(self, query: Mapping[str, Any]) -> None:
        refresh = self.refresh
        if refresh == "wait_for":
            refresh = True
        for stream_name in self._get_data_stream_names() + self._get_index_names():
            try:
                response = self.db.delete_by_query(
                    index=stream_name,
                    body={"query": query},
                    conflicts="proceed",
                    refresh=bool(refresh),
                )
            except Exception as exception:
                if not self._is_not_found(exception):
                    raise
                continue
            body = self._response_body(response)
            if not isinstance(body, Mapping):
                continue
            if (
                body.get("timed_out")
                or body.get("failures")
                or body.get("version_conflicts")
            ):
                raise TimeseriesWriteException(
                    f'Incomplete deletion on "{stream_name}": {body}'
                )

    def delete_series(
        self, key: str | None = None, tags: TimeseriesTags | None = None
    ) -> None:
        if not key and not tags:
            raise ValueError("delete_series requires at least one of key or tags")
        self._delete_by_query(self._build_base_query(key=key, tags=tags))

    def delete_metric_data(
        self,
        key: str | None = None,
        tags: TimeseriesTags | None = None,
        timestamp: Any = None,
    ) -> None:
        """Deletes metric data based on measurement and tags.

        If ``timestamp`` is passed, only the data written at that specific
        time is deleted.
        """
        self._delete_by_query(
            self._build_base_query(key=key, tags=tags, timestamp=timestamp)
        )
