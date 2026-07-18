import logging
import re
from collections.abc import Iterator, Mapping, Sequence
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.utils.dateparse import parse_datetime
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from elasticsearch import ApiError, Elasticsearch, NotFoundError, TransportError
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
        if isinstance(value, datetime):
            dt = value
        elif isinstance(value, str):
            dt = parse_datetime(value)
            if dt is None:
                return value
        else:
            return value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if self.precision is None:
            return dt.isoformat().replace("+00:00", "Z")
        timestamp = dt.timestamp()
        if self.precision == "s":
            return int(timestamp)
        if self.precision == "ms":
            return int(timestamp * 1000)
        if self.precision == "u":
            return int(timestamp * 1000000)
        if self.precision == "ns":
            return int(timestamp * 1000000000)
        return timestamp

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
    _OPERATORS = ("=", "!=", "<", ">", "<=", ">=")
    _AGGREGATE = (
        "avg",
        "cardinality",
        "count",
        "date_histogram",
        "extended_stats",
        "histogram",
        "max",
        "min",
        "percentiles",
        "stats",
        "sum",
        "terms",
        "value_count",
    )
    _DURATION_PATTERN = re.compile(r"(?:\d+[smhdw])+")
    _DURATION_PART_PATTERN = re.compile(r"(\d+)([smhdw])")
    _DEFAULT_ROLLOVER_SECONDS = 30 * 24 * 60 * 60
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
        has_cloud_id = bool(config.get("CLOUD_ID"))
        has_url = bool(config.get("URL"))
        has_host_port = all(config.get(field) for field in ("HOST", "PORT"))
        if not has_cloud_id and not has_url and not has_host_port:
            raise ImproperlyConfigured(
                'Elasticsearch TIMESERIES_DATABASE must define "CLOUD_ID", '
                '"URL", or both "HOST" and "PORT".'
            )
        return config

    def __init__(self, db_name: str | None = None) -> None:
        self.db_name = db_name or TIMESERIES_DB["NAME"]
        self._ensured_streams = set()

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

    def _get_retention_policy_name(self, retention_policy=None) -> str:
        if not retention_policy or retention_policy == "autogen":
            return "autogen"
        return str(retention_policy)

    def _get_stream_name(self, retention_policy=None) -> str:
        retention_policy = self._get_retention_policy_name(retention_policy)
        if retention_policy == "autogen":
            return self.db_name
        return f"{self.db_name}-{retention_policy}"

    def _get_policy_name(self, retention_policy=None) -> str:
        return f"{self.db_name}-{self._get_retention_policy_name(retention_policy)}-ilm"

    def _get_template_name(self, retention_policy=None) -> str:
        return f"{self._get_stream_name(retention_policy)}-template"

    def _is_own_stream(self, name: str) -> bool:
        return name == self.db_name or name.startswith(f"{self.db_name}-")

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
        return "resource_already_exists_exception" in str(exception)

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
        rollover_seconds = duration_seconds or self._DEFAULT_ROLLOVER_SECONDS
        rollover_seconds = min(rollover_seconds, self._DEFAULT_ROLLOVER_SECONDS)
        policy = {
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
            }
        }
        if duration_seconds:
            policy["phases"]["delete"] = {
                "min_age": f"{duration_seconds}s",
                "actions": {"delete": {}},
            }
        return policy

    def _put_lifecycle_policy(self, name: str, policy: Mapping[str, Any]) -> None:
        try:
            self.db.ilm.put_lifecycle(name=name, policy=policy)
        except TypeError:
            self.db.ilm.put_lifecycle(name=name, body={"policy": policy})

    def _build_index_template_body(self, retention_policy=None) -> dict[str, Any]:
        stream_name = self._get_stream_name(retention_policy)
        return {
            "index_patterns": [stream_name],
            "data_stream": {},
            "priority": self.options.get("template_priority", 500),
            "template": {
                "settings": {
                    "index.mode": "time_series",
                    "index.lifecycle.name": self._get_policy_name(retention_policy),
                    "index.routing_path": ["measurement", "tags.*"],
                },
                "mappings": {
                    "dynamic": True,
                    "dynamic_templates": [
                        {
                            "tag_values": {
                                "path_match": "tags.*",
                                "mapping": {
                                    "type": "keyword",
                                    "time_series_dimension": True,
                                    "ignore_above": 2048,
                                },
                            }
                        },
                        {
                            "field_strings": {
                                "path_match": "fields.*",
                                "match_mapping_type": "string",
                                "mapping": {
                                    "type": "keyword",
                                    "ignore_above": 8192,
                                },
                            }
                        },
                        {
                            "field_longs": {
                                "path_match": "fields.*",
                                "match_mapping_type": "long",
                                "mapping": {
                                    "type": "double",
                                    "time_series_metric": "gauge",
                                },
                            }
                        },
                        {
                            "field_doubles": {
                                "path_match": "fields.*",
                                "match_mapping_type": "double",
                                "mapping": {
                                    "type": "double",
                                    "time_series_metric": "gauge",
                                },
                            }
                        },
                    ],
                    "properties": {
                        "@timestamp": {"type": "date"},
                        "measurement": {
                            "type": "keyword",
                            "time_series_dimension": True,
                        },
                        "openwisp_doc_count": {
                            "type": "long",
                            "time_series_metric": "gauge",
                        },
                        "tags": {"type": "object", "dynamic": True},
                        "fields": {"type": "object", "dynamic": True},
                    },
                },
                "lifecycle": {"enabled": True},
            },
            "_meta": {"description": "OpenWISP Monitoring Elasticsearch TSDS data"},
        }

    def _put_index_template(self, retention_policy=None) -> None:
        name = self._get_template_name(retention_policy)
        body = self._build_index_template_body(retention_policy)
        try:
            self.db.indices.put_index_template(name=name, **body)
        except TypeError:
            self.db.indices.put_index_template(name=name, body=body)

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
    ):
        stream_name = self._get_stream_name(retention_policy)
        cache_key = (stream_name, duration)
        if cache_key in self._ensured_streams:
            return
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
        self._ensured_streams.add(cache_key)

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
        self._delete_index_templates()
        self._delete_lifecycle_policies()
        self._ensured_streams = set()
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
            if self._is_own_stream(stream["name"])
        ]

    def _delete_index_templates(self) -> None:
        try:
            response = self.db.indices.get_index_template(
                name=f"{self.db_name}*-template"
            )
        except Exception as exception:
            if self._is_not_found(exception):
                return
            raise
        response = self._response_body(response)
        template_names = [
            template["name"]
            for template in response.get("index_templates", [])
            if template["name"] == self._get_template_name()
            or (
                template["name"].startswith(f"{self.db_name}-")
                and template["name"].endswith("-template")
            )
        ]
        for template_name in template_names:
            try:
                self.db.indices.delete_index_template(name=template_name)
            except Exception as exception:
                if not self._is_not_found(exception):
                    raise

    def _delete_lifecycle_policies(self) -> None:
        for policy_name in self._get_lifecycle_policy_names():
            try:
                self.db.ilm.delete_lifecycle(name=policy_name)
            except Exception as exception:
                if not self._is_not_found(exception):
                    raise

    def _get_lifecycle_policy_names(self) -> list[str]:
        try:
            response = self.db.ilm.get_lifecycle(name=f"{self.db_name}-*-ilm")
        except Exception as exception:
            if self._is_not_found(exception):
                return []
            raise
        response = self._response_body(response)
        return [
            name
            for name in response.keys()
            if name.startswith(f"{self.db_name}-") and name.endswith("-ilm")
        ]

    @retry
    def create_or_alter_retention_policy(self, name: str, duration: str) -> None:
        self._ensure_data_stream_resources(retention_policy=name, duration=duration)
        logger.debug(
            'Created/updated Elasticsearch retention policy "%s" with duration %s',
            name,
            duration,
        )

    @retry
    def get_list_retention_policies(self) -> list[TimeseriesPoint]:
        policies = []
        for policy_name in self._get_lifecycle_policy_names():
            retention_policy = policy_name[len(self.db_name) + 1 : -len("-ilm")]
            try:
                body = self.db.ilm.get_lifecycle(name=policy_name)
            except Exception as exception:
                if self._is_not_found(exception):
                    continue
                raise
            body = self._response_body(body)
            phases = body.get(policy_name, {}).get("policy", {}).get("phases", {})
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
        timestamp = timestamp or now()
        parsed_timestamp = self._parse_timestamp(timestamp)
        if parsed_timestamp is not None:
            return self._serialize_timestamp(
                parsed_timestamp, timezone_name=timezone_name
            )
        return timestamp

    def _normalize_time(self, value, precision="s"):
        if isinstance(value, datetime):
            dt = value
        elif isinstance(value, str):
            dt = parse_datetime(value)
            if dt is None:
                return value
        else:
            return value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if precision is None:
            return dt.isoformat().replace("+00:00", "Z")
        timestamp = dt.timestamp()
        if precision == "s":
            return int(timestamp)
        if precision == "ms":
            return int(timestamp * 1000)
        if precision == "u":
            return int(timestamp * 1000000)
        if precision == "ns":
            return int(timestamp * 1000000000)
        return timestamp

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

    def _build_document(self, name, values, **kwargs) -> dict[str, Any]:
        return {
            "@timestamp": self._get_timestamp(kwargs.get("timestamp")),
            "measurement": name,
            "openwisp_doc_count": 1,
            "tags": dict(kwargs.get("tags") or {}),
            "fields": dict(values or {}),
        }

    def _handle_write_exception(self, exception) -> None:
        logger.warning("Error writing to Elasticsearch: %s", exception)
        raise TimeseriesWriteException from exception

    def write(self, name: str, values: TimeseriesFields, **kwargs: Any) -> None:
        self._check_database_kwarg(kwargs.get("database"))
        retention_policy = kwargs.get("retention_policy")
        self._ensure_data_stream_resources(retention_policy)
        document = self._build_document(name, values, **kwargs)
        try:
            self.db.index(
                index=self._get_stream_name(retention_policy),
                document=document,
                op_type="create",
                refresh=self.refresh,
            )
        except Exception as exception:
            self._handle_write_exception(exception)

    def batch_write(self, metric_data: Sequence[BatchWritePayload]) -> None:
        actions = []
        ensured_retention_policies = set()
        checked_databases = set()
        for data in metric_data:
            database = data.get("database")
            if database not in checked_databases:
                self._check_database_kwarg(database)
                checked_databases.add(database)
            retention_policy = data.get("retention_policy")
            if retention_policy not in ensured_retention_policies:
                self._ensure_data_stream_resources(retention_policy)
                ensured_retention_policies.add(retention_policy)
            actions.append(
                {
                    "_op_type": "create",
                    "_index": self._get_stream_name(retention_policy),
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
                self.db, actions, refresh=self.refresh
            )  # https://elasticsearch-py.readthedocs.io/en/v8.12.1/helpers.html#bulk-helpers
        except Exception as exception:
            self._handle_write_exception(exception)

    def _empty_search_response(self) -> dict[str, Any]:
        return {"hits": {"total": {"value": 0}, "hits": []}}

    @retry
    def query(
        self, query, precision: str | None = None, **kwargs: Any
    ) -> QueryResultSet:
        if not isinstance(query, Mapping):
            raise self.client_error("Elasticsearch queries must be dictionaries.")
        query = deepcopy(query)
        index = (
            kwargs.get("index")
            or query.pop("__index", None)
            or query.pop("index", None)
            or self._get_stream_name(query.pop("__retention_policy", None))
        )
        for key in list(query.keys()):
            if key.startswith("__openwisp_"):
                query.pop(key)
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
        field_name = f"fields.{field}"
        if op == "=":
            return {"term": {field_name: value}}
        if op == "!=":
            return {"bool": {"must_not": [{"term": {field_name: value}}]}}
        range_operator = {">": "gt", ">=": "gte", "<": "lt", "<=": "lte"}[op]
        return {"range": {field_name: {range_operator: value}}}

    def _build_base_query(
        self,
        key: str | None = None,
        tags: TimeseriesTags | None = None,
        since=None,
        where: Sequence[Sequence[Any]] | None = None,
    ) -> dict[str, Any]:
        filters = []
        measurement_filter = self._build_measurement_filter(key) if key else None
        if measurement_filter:
            filters.append(measurement_filter)
        if since:
            filters.append(
                {"range": {"@timestamp": {"gte": self._get_timestamp(since)}}}
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
        point = {
            "time": self._normalize_time(
                document.get("@timestamp"), precision=precision
            )
        }
        if include_tags:
            point.update(document.get("tags") or {})
        values = document.get("fields") or {}
        if not fields or fields == ["*"]:
            point.update(values)
            return point
        for field in fields:
            if field in values:
                point[field] = values[field]
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
        response = self.query(
            {
                "size": 0,
                "query": self._build_base_query(
                    key=key, tags=tags, since=since, where=where
                ),
                "aggs": {"count": {"cardinality": {"field": f"fields.{field}"}}},
                "__retention_policy": retention_policy,
            },
            precision=precision,
        )
        value = response.get("aggregations", {}).get("count", {}).get("value", 0)
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
            sort = [{"@timestamp": {"order": "asc"}}]
        elif order == "-time":
            sort = [{"@timestamp": {"order": "desc"}}]
        else:
            message = _(
                'Invalid order "%(order)s" passed.\n'
                'You may pass "time" / "-time" to get result sorted '
                "in ascending /descending order respectively."
            ) % {"order": order}
            raise self.client_error(message)
        query = {
            "query": self._build_base_query(
                key=key,
                tags=tags,
                since=kwargs.get("since"),
                where=where,
            ),
            "sort": sort,
            "__retention_policy": retention_policy,
        }
        if limit:
            query["size"] = int(limit)
        else:
            query["size"] = int(self.options.get("read_size", 10000))
        response = self.query(query, precision=precision)
        return [
            self._document_to_point(
                hit.get("_source", {}),
                fields=fields,
                precision=precision,
            )
            for hit in self._get_hits(response)
        ]

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
        if value in (None, "", "__all__"):
            return None
        tag_field = f"tags.{field}"
        if isinstance(value, (list, tuple)):
            values = [str(item) for item in value if item != "__all__"]
            if not values:
                return None
            return {"terms": {tag_field: values}}
        return {"term": {tag_field: str(value)}}

    def _build_chart_base_query(self, params, timezone_name=None):
        filters = []
        measurement_filter = self._build_measurement_filter(params.get("key"))
        if measurement_filter:
            filters.append(measurement_filter)
        time_filter = {}
        if params.get("time"):
            time_filter["gte"] = self._get_timestamp(
                params["time"], timezone_name=timezone_name
            )
        if params.get("end_date"):
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

    def _normalize_chart_window(self, time, group_map):
        return str(group_map.get(time, time) or "1d")

    def _format_chart_metrics(self, query, params):
        format_params = {**params}
        metrics = self._format_query_mapping(query.get("metrics", []), format_params)
        return [metric for metric in metrics if metric.get("field")]

    def _build_metric_aggregation(self, metric):
        field = f"fields.{metric['field']}"
        aggregation = metric.get("agg", "avg")
        if aggregation == "sum":
            return {"sum": {"field": field}}
        if aggregation == "cardinality":
            return {"cardinality": {"field": field}}
        if aggregation == "mode":
            return {"terms": {"field": field, "size": 1}}
        return {"avg": {"field": field}}

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
    ):
        metrics = self._format_chart_metrics(query, params)
        body = {
            "size": 0,
            "query": self._build_chart_base_query(params, timezone_name=timezone),
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
        if timezone:
            histogram["time_zone"] = timezone
        body["aggs"] = {
            "timeseries": {
                "date_histogram": histogram,
                "aggs": metric_aggs,
            }
        }
        return body

    def _normalize_raw_chart_fields(self, query, params, fields=None):
        if fields:
            return list(fields)
        field = self._format_query_mapping(query.get("field"), params)
        if not field or field == "{fields}":
            return ["*"]
        return [field]

    def _build_raw_chart_query(self, query, params, fields=None, timezone=None):
        selected_fields = self._normalize_raw_chart_fields(query, params, fields)
        return {
            "size": int(self.options.get("read_size", 10000)),
            "query": self._build_chart_base_query(params, timezone_name=timezone),
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
            return self._is_aggregate(query)
        response = self._response_body(response)
        if not response.get("valid", False):
            message = response.get("error") or _("Invalid Elasticsearch query")
            raise ValidationError({"configuration": message})
        return self._is_aggregate(query)

    def _is_aggregate(self, query) -> bool:
        if not isinstance(query, Mapping):
            return False
        if self._is_openwisp_query(query):
            return bool(query.get("aggregate", query.get("__openwisp_aggregate", True)))
        aggregations = query.get("aggs") or query.get("aggregations")
        if not isinstance(aggregations, Mapping):
            return False
        return self._contains_aggregate(aggregations)

    def _contains_aggregate(self, value) -> bool:
        if isinstance(value, Mapping):
            if any(key in self._AGGREGATE for key in value.keys()):
                return True
            return any(self._contains_aggregate(item) for item in value.values())
        if isinstance(value, list):
            return any(self._contains_aggregate(item) for item in value)
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
        search = {
            "size": int(self.options.get("top_fields_read_size", 10000)),
            "_source": ["fields"],
            "query": self._build_chart_base_query(params, timezone_name=timezone),
            "__index": self._get_stream_name(params.get("retention_policy")),
        }
        response = self.query(search, precision="s")
        totals = {}
        for hit in self._get_hits(response):
            fields = (hit.get("_source") or {}).get("fields") or {}
            for field, value in fields.items():
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    continue
                totals[field] = totals.get(field, 0) + value
        sorted_fields = sorted(totals.items(), key=lambda item: item[1], reverse=True)
        return [field for field, _value in sorted_fields[:number]]

    def _round_chart_value(self, value):
        if value >= 0:
            return float(int(value + 0.5))
        return float(int(value - 0.5))

    def _extract_chart_metric_value(self, aggregation, metric):
        metric_aggregation = aggregation.get(metric["name"], {})
        if metric.get("agg") == "mode":
            buckets = metric_aggregation.get("buckets", [])
            value = buckets[0]["key"] if buckets else None
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

    def _format_histogram_time(self, bucket, precision):
        if "key" not in bucket:
            return None
        value = datetime.fromtimestamp(bucket["key"] / 1000, tz=timezone.utc)
        return self._normalize_time(value, precision=precision)

    def _get_chart_points(self, response, query, precision="s"):
        metrics = query.get("__openwisp_metrics", [])
        aggregations = response.get("aggregations", {})
        if query.get("__openwisp_summary"):
            return [self._build_chart_point(aggregations, metrics)]
        buckets = aggregations.get("timeseries", {}).get("buckets", [])
        return [
            self._build_chart_point(
                bucket,
                metrics,
                time_value=self._format_histogram_time(bucket, precision),
            )
            for bucket in buckets
        ]

    def get_list_query(
        self, query: Mapping[str, Any], precision: str = "s"
    ) -> list[TimeseriesPoint]:
        if (
            isinstance(query, Mapping)
            and query.get("_openwisp_query_type") == "device_data"
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
        response = self.query(query, precision=precision)
        fields = query.get("__openwisp_fields") if isinstance(query, Mapping) else None
        return [
            self._document_to_point(
                hit.get("_source", {}),
                fields=fields,
                precision=precision,
                include_tags=False,
            )
            for hit in self._get_hits(response)
        ]

    def get_device_data_query(
        self,
        retention_policy: str,
        measurement: str,
        pk: str,
    ) -> Mapping[str, str]:
        return {
            "_openwisp_query_type": "device_data",
            "retention_policy": retention_policy,
            "measurement": measurement,
            "pk": str(pk),
        }

    @retry
    def _delete_by_query(self, query: Mapping[str, Any]) -> None:
        refresh = self.refresh
        if refresh == "wait_for":
            refresh = True
        for stream_name in self._get_data_stream_names():
            try:
                self.db.delete_by_query(
                    index=stream_name,
                    body={"query": query},
                    conflicts="proceed",
                    refresh=bool(refresh),
                )
            except Exception as exception:
                if not self._is_not_found(exception):
                    raise

    @retry
    def delete_series(
        self, key: str | None = None, tags: TimeseriesTags | None = None
    ) -> None:
        if not key and not tags:
            raise ValueError("delete_series requires at least one of key or tags")
        self._delete_by_query(self._build_base_query(key=key, tags=tags))

    def delete_metric_data(
        self, key: str | None = None, tags: TimeseriesTags | None = None
    ) -> None:
        self._delete_by_query(self._build_base_query(key=key, tags=tags))
