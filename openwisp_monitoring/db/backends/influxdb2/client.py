import logging
import re
from collections.abc import Iterator, Mapping, Sequence
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from influxdb_client import InfluxDBClient
from influxdb_client.client.exceptions import InfluxDBError
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.domain import BucketRetentionRules

from openwisp_monitoring.device import settings as device_settings
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

FLUX_METADATA_FIELDS = {
    "result",
    "table",
    "_start",
    "_stop",
    "_time",
    "_measurement",
    "_field",
    "_value",
}

SeriesTags = dict[str, Any]
SeriesTagSet = frozenset[tuple[str, Any]]
SeriesCacheKey = tuple[str, SeriesTagSet]
SeriesKey = tuple[str, SeriesTags | None]
SeriesCache = dict[SeriesCacheKey, list[TimeseriesPoint]]


class QueryResultSet:
    """
    Wrapper to mimic InfluxDB 1.x ResultSet behavior for InfluxDB 2.x responses.
    This ensures backward compatibility with existing code that expects
    ResultSet objects with get_points() and keys() methods.
    v1 groups results by (measurement, tags) pairs. This implementation
    mimics that structure for backward compatibility.
    """

    def __init__(self, points: list[TimeseriesPoint]) -> None:
        """
        Initialize with a list of point dictionaries from InfluxDB 2.x
        Args:
            points: List of data point dictionaries with structure:
                   {"_measurement": str, "_field": str, "_value": any,
                    "time": datetime, ...other_tags}
        """
        self.points = points
        self._series_cache: SeriesCache | None = None

    def _group_by_measurement_tags(self) -> SeriesCache:
        """
        Group points by (measurement, tags) to mimic v1 structure.
        Returns a dict: {(measurement, frozenset(tags.items())): [points]}
        """
        if self._series_cache is not None:
            return self._series_cache
        series_dict: SeriesCache = {}
        for point in self.points:
            measurement = point.get("_measurement", "results")
            # Extract tags (all keys except special fields)
            special_fields = {"_measurement", "_field", "_value", "time", "__raw_time"}
            tags: SeriesTags = {}
            for key, value in point.items():
                if key not in special_fields:
                    tags[key] = value
            # Use frozenset of tags for hashable key
            tags_key = frozenset(tags.items()) if tags else frozenset()
            series_key = (measurement, tags_key)
            if series_key not in series_dict:
                series_dict[series_key] = []
            series_dict[series_key].append(point)
        self._series_cache = series_dict
        return series_dict

    def get_points(
        self, measurement: str | None = None, tags: TimeseriesTags | None = None
    ) -> Iterator[TimeseriesPoint]:
        """
        Yield points filtered by measurement and tags.
        Mimics v1 ResultSet.get_points() which is a generator.
        Args:
            measurement: Filter by measurement name (optional)
            tags: Filter by tags dict (optional)
        Yields:
            Point dictionaries
        """
        series_dict = self._group_by_measurement_tags()
        for (series_measurement, series_tags_frozen), points in series_dict.items():
            series_tags = dict(series_tags_frozen) if series_tags_frozen else {}
            # Check measurement match
            if measurement is not None and measurement != series_measurement:
                continue
            # Check tags match
            if tags is not None:
                if not self._tag_matches(series_tags, tags):
                    continue
            # Yield all points from this series
            for point in points:
                yield point

    def keys(self) -> list[SeriesKey]:
        """
        Return list of (measurement, tags) tuples.
        Mimics v1 ResultSet.keys() which returns list of
        (measurement_name, tags_dict) tuples.
        """
        series_dict = self._group_by_measurement_tags()
        keys: list[SeriesKey] = []
        for measurement, tags_frozen in series_dict.keys():
            tags_dict = dict(tags_frozen) if tags_frozen else None
            keys.append((measurement, tags_dict))
        return keys

    def items(self) -> list[tuple[SeriesKey, Iterator[TimeseriesPoint]]]:
        """
        Return list of (key, points_generator) tuples.
        Mimics v1 ResultSet.items().
        """
        series_dict = self._group_by_measurement_tags()
        items: list[tuple[SeriesKey, Iterator[TimeseriesPoint]]] = []
        for (measurement, tags_frozen), points in series_dict.items():
            tags_dict = dict(tags_frozen) if tags_frozen else None
            key = (measurement, tags_dict)
            # Create generator from points
            points_gen = (point for point in points)
            items.append((key, points_gen))
        return items

    @staticmethod
    def _tag_matches(series_tags: TimeseriesTags, filter_tags: TimeseriesTags) -> bool:
        """Check if all key/values in filter match in tags."""
        for tag_name, tag_value in filter_tags.items():
            if series_tags.get(tag_name) != tag_value:
                return False
        return True

    def __iter__(self) -> Iterator[TimeseriesPoint]:
        """Yield points like v1 ResultSet."""
        yield from self.get_points()

    def __len__(self) -> int:
        """Return the number of series (measurement, tags) combinations."""
        return len(self.keys())

    def __repr__(self) -> str:
        """Representation of ResultSet object."""
        items = []
        for key, points in self.items():
            items.append("'%s': %s" % (key, list(points)))
        return "ResultSet({%s})" % ", ".join(items)


class DatabaseClient(BaseTimeseriesClient):
    """InfluxDB 2.0 client for timeseries database operations."""

    _AGGREGATE = ["mean", "sum", "count", "max", "min", "mode", "stddev"]
    backend_name = "influxdb2"
    client_error = InfluxDBError
    required_settings = ("BACKEND", "USER", "PASSWORD", "NAME")
    _FORBIDDEN = ["drop", "delete", "alter", "create", "into"]
    _OPERATORS = ["=", "!=", "<", ">", "<=", ">="]
    _FLUX_STRING_ESCAPES = {
        "\\": "\\\\",
        '"': '\\"',
        "\n": "\\n",
        "\r": "\\r",
        "\t": "\\t",
        "${": r"\${",
    }
    _FLUX_STRING_PATTERN = re.compile(
        r'\$\{|["\\\n\r\t]|[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]'
    )
    _DELETE_PREDICATE_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

    @classmethod
    def validate_settings(cls, config: Mapping[str, Any] | None) -> Mapping[str, Any]:
        if config is None or not hasattr(config, "__contains__"):
            raise ImproperlyConfigured("No TIMESERIES_DATABASE specified in settings")
        for field in cls.required_settings:
            if field not in config:
                raise ImproperlyConfigured(
                    f'"{field}" field is not declared in TIMESERIES_DATABASE'
                )
        has_url = bool(config.get("URL"))
        has_host_port = all(config.get(field) for field in ("HOST", "PORT"))
        if not has_url and not has_host_port:
            raise ImproperlyConfigured(
                'InfluxDB2 TIMESERIES_DATABASE must define either "URL" '
                'or both "HOST" and "PORT".'
            )
        return config

    def __init__(self, db_name: str | None = None) -> None:
        """Initialize InfluxDB 2 client.

        Args:
            db_name: Bucket name (equivalent to database in InfluxDB 1.x)
        """
        self._db = None
        self.db_name = db_name or TIMESERIES_DB["NAME"]
        self.user = TIMESERIES_DB.get("USER", "openwisp")
        self.password = TIMESERIES_DB.get("PASSWORD", "")

    def _close_cached_client(self) -> None:
        client = self.__dict__.get("db")
        close = getattr(client, "close", None)
        try:
            if callable(close):
                close()
        except Exception as exception:
            logger.debug("Error while closing InfluxDB2 client: %s", exception)

    def reset(self, db_name: str | None = None) -> None:
        self._close_cached_client()
        super().reset(db_name=db_name)
        for attr in ("db", "_write_api", "_query_api", "_delete_api", "use_udp"):
            self.__dict__.pop(attr, None)

    def close(self) -> None:
        self.reset()

    @retry
    def create_database(self) -> None:
        """Creates bucket if necessary."""
        api = self.db.buckets_api()
        try:
            bucket = api.find_bucket_by_name(self.db_name)
            if bucket:
                logger.debug(f'InfluxDB2 bucket "{self.db_name}" already exists')
                return
        except self.client_error:
            pass
        api.create_bucket(bucket_name=self.db_name, org=self.user)
        logger.debug(f'Created InfluxDB2 bucket "{self.db_name}"')

    @retry
    def drop_database(self) -> None:
        """Drops known buckets if they exist."""
        api = self.db.buckets_api()
        for bucket_name in self._get_known_bucket_names():
            try:
                bucket = api.find_bucket_by_name(bucket_name)
                if bucket:
                    api.delete_bucket(bucket)
                    logger.debug(f'Dropped InfluxDB2 bucket "{bucket_name}"')
            except self.client_error:
                logger.debug(f'InfluxDB2 bucket "{bucket_name}" not found')

    @cached_property
    def db(self) -> InfluxDBClient:
        """Returns an InfluxDBClient instance."""
        url = (
            TIMESERIES_DB.get("URL")
            or f"http://{TIMESERIES_DB['HOST']}:{TIMESERIES_DB['PORT']}"
        )
        if urlparse(url).scheme == "http":
            logger.warning(
                'Using insecure HTTP for InfluxDB2 at "%s". Consider '
                'switching TIMESERIES_DATABASE["URL"] to https:// when '
                "running outside local development.",
                url,
            )
        return InfluxDBClient(url=url, token=self.password, org=self.user)

    @cached_property
    def _write_api(self):
        """Returns write API instance."""
        # docs:
        # https://influxdb-client.readthedocs.io/en/stable/api.html#influxdb_client.WriteApi
        return self.db.write_api(write_options=SYNCHRONOUS)

    @cached_property
    def _query_api(self):
        """Returns query API instance."""
        return self.db.query_api()

    @cached_property
    def _delete_api(self):
        """Returns delete API instance."""
        return self.db.delete_api()

    @cached_property
    def use_udp(self) -> bool:
        return False

    def _get_bucket_name(self, retention_policy=None):
        if not retention_policy or retention_policy == "autogen":
            return self.db_name
        return f"{self.db_name}_{retention_policy}"

    def _get_known_bucket_names(self):
        return [self._get_bucket_name(), self._get_bucket_name("short")]

    def _get_retention_policy_name(self, bucket_name):
        if bucket_name == self.db_name:
            return "autogen"
        prefix = f"{self.db_name}_"
        if bucket_name.startswith(prefix):
            prefix_length = len(prefix)
            return bucket_name[prefix_length:]
        return bucket_name

    def _get_bucket_retention_duration(self, bucket):
        if bucket and bucket.retention_rules:
            return f"{bucket.retention_rules[0].every_seconds}s"
        return "0s"

    @retry
    def create_or_alter_retention_policy(self, name: str, duration: str) -> None:
        """Creates or alters a bucket matching the retention policy."""
        api = self.db.buckets_api()
        bucket_name = self._get_bucket_name(name)
        duration_seconds = self._duration_to_seconds(duration)
        retention_rules = [
            BucketRetentionRules(type="expire", every_seconds=duration_seconds)
        ]
        try:
            bucket = api.find_bucket_by_name(bucket_name)
        except self.client_error as exception:
            logger.warning(
                f'Could not inspect InfluxDB2 bucket "{bucket_name}": {exception}'
            )
            return
        if not bucket:
            api.create_bucket(
                bucket_name=bucket_name,
                org=self.user,
                retention_rules=retention_rules,
            )
            logger.debug(
                f'Created InfluxDB2 bucket "{bucket_name}" for retention policy '
                f'"{name}" with duration {duration}'
            )
            return
        bucket.retention_rules = retention_rules
        try:
            api.update_bucket(bucket=bucket)
        except self.client_error as exception:
            logger.warning(f"Could not update InfluxDB2 bucket retention: {exception}")
            return
        logger.debug(
            f'Created/updated InfluxDB2 bucket "{bucket_name}" for retention policy '
            f'"{name}" with duration {duration}'
        )

    def _duration_to_seconds(self, duration):
        """Converts duration string (eg '30d' or '26280h0m0s') to seconds."""
        mapping = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
        duration_parts = re.findall(r"(\d+)([smhdw])", duration)
        if not duration_parts:
            raise ValueError(f'Invalid duration "{duration}"')
        return sum(int(value) * mapping[unit] for value, unit in duration_parts)

    def _get_timestamp(self, timestamp=None):
        """Returns ISO format timestamp."""
        timestamp = timestamp or now()
        if isinstance(timestamp, datetime):
            return timestamp.isoformat()
        return timestamp

    def _clean_operator(self, op):
        if op not in self._OPERATORS:
            raise self.client_error(
                f'Invalid operator "{op}" passed.\n'
                f"Valid operators are: {', '.join(self._OPERATORS)}"
            )
        return "==" if op == "=" else op

    @classmethod
    def _escape_flux_match(cls, match):
        token = match.group(0)
        escaped = cls._FLUX_STRING_ESCAPES.get(token)
        if escaped is not None:
            return escaped
        return "".join(f"\\x{byte:02x}" for byte in token.encode("utf-8"))

    @classmethod
    def _escape_flux_string(cls, value):
        return cls._FLUX_STRING_PATTERN.sub(cls._escape_flux_match, str(value))

    def _format_flux_string(self, value):
        return f'"{self._escape_flux_string(value)}"'

    def _format_flux_property_access(self, key):
        return f"r[{self._format_flux_string(key)}]"

    @classmethod
    def _validate_delete_predicate_key(cls, key):
        if not cls._DELETE_PREDICATE_KEY_PATTERN.fullmatch(str(key)):
            raise ValueError(f'Invalid delete predicate key "{key}"')
        return key

    def _format_flux_value(self, value):
        if isinstance(value, datetime):
            return f'"{self._get_timestamp(value)}"'
        if isinstance(value, str):
            return self._format_flux_string(value)
        if isinstance(value, bool):
            return str(value).lower()
        return value

    def _format_flux_time(self, value):
        if isinstance(value, datetime):
            value = self._get_timestamp(value)
        if isinstance(value, str):
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                value = f"{value}T00:00:00"
            if "T" not in value and " " in value:
                value = value.replace(" ", "T", 1)
            if value.endswith("Z"):
                return f'time(v: "{value}")'
            if (
                "+" not in value[10:]
                and "-" not in value[10:]
                and not value.endswith("Z")
            ):
                value = f"{value}Z"
            return f'time(v: "{value}")'
        return value

    def _get_open_range_stop(self, since):
        if isinstance(since, datetime):
            return since + timedelta(days=3650)
        return datetime(2100, 1, 1, tzinfo=timezone.utc)

    def _normalize_chart_window(self, time_value, group_map=None):
        if group_map and time_value in group_map:
            return group_map[time_value]
        if isinstance(time_value, (int, float)):
            return f"{max(int(time_value), 1)}m"
        if isinstance(time_value, str) and re.fullmatch(r"\d+", time_value):
            return f"{max(int(time_value), 1)}m"
        return time_value

    def _normalize_chart_start_range(self, time_value):
        if isinstance(time_value, (int, float)):
            return f"-{self._normalize_chart_window(time_value)}"
        if isinstance(time_value, str) and re.fullmatch(r"\d+", time_value):
            return f"-{self._normalize_chart_window(time_value)}"
        return self._format_flux_time(time_value)

    def _normalize_record_time(self, record_time, precision="s"):
        if not isinstance(record_time, datetime):
            return record_time
        if precision is None:
            return record_time.isoformat().replace("+00:00", "Z")
        timestamp = record_time.timestamp()
        if precision == "s":
            return int(timestamp)
        if precision == "ms":
            return int(timestamp * 1000)
        if precision == "u":
            return int(timestamp * 1000000)
        if precision == "ns":
            return int(timestamp * 1000000000)
        return timestamp

    def _get_record_time(self, record):
        return (
            record.values.get("_time")
            or record.values.get("_stop")
            or record.values.get("_start")
        )

    def _is_retention_policy_violation(self, exception):
        message = str(exception).lower()
        return "retention policy" in message and "dropped" in message

    def _ensure_bucket_exists(self, bucket_name):
        if bucket_name == self.db_name:
            self.create_database()
            return
        if bucket_name == self._get_bucket_name("short"):
            self.create_or_alter_retention_policy(
                "short", device_settings.SHORT_RETENTION_POLICY
            )

    def validate_query(self, query: str) -> bool:
        for word in self._FORBIDDEN:
            if re.search(rf"\b{word}\b", query, re.IGNORECASE):
                msg = _('the word "%(word)s" is not allowed') % {"word": word.upper()}
                raise ValidationError({"configuration": msg})
        return self._is_aggregate(query)

    def _is_aggregate(self, query):
        query = query.lower()
        if any(f"{word}(" in query for word in self._AGGREGATE):
            return True
        return any(
            re.search(
                rf"aggregatewindow\([^)]*fn:\s*{word}(?:\s*[,)])", query, re.IGNORECASE
            )
            for word in self._AGGREGATE
        )

    def write(self, name: str, values: TimeseriesFields, **kwargs: Any) -> None:
        timestamp = self._get_timestamp(timestamp=kwargs.get("timestamp"))
        if kwargs.get("database") and kwargs.get("database") != self.db_name:
            logger.warning(
                f'Parameter "database" is ignored in InfluxDB 2.0. '
                f'Using bucket "{self.db_name}"'
            )
        bucket = self._get_bucket_name(kwargs.get("retention_policy"))
        point = {
            "measurement": name,
            "tags": kwargs.get("tags", {}),
            "fields": values,
            "time": timestamp,
        }
        try:
            self._write_api.write(
                bucket=bucket,
                org=self.user,
                record=point,
            )
        except Exception as exception:
            if self._is_retention_policy_violation(exception):
                logger.warning(
                    "Ignoring InfluxDB2 write dropped by retention policy: %s",
                    exception,
                )
                return
            logger.warning(f"Error writing to InfluxDB2: {exception}")
            raise TimeseriesWriteException

    def batch_write(self, metric_data: Sequence[BatchWritePayload]) -> None:
        """Write multiple data points in batch."""
        points_by_bucket = {}
        for data in metric_data:
            if data.get("database") and data.get("database") != self.db_name:
                logger.warning(
                    f'Parameter "database" is ignored in InfluxDB 2.0. '
                    f'Writing to bucket "{self.db_name}"'
                )
            bucket = self._get_bucket_name(data.get("retention_policy"))
            timestamp = self._get_timestamp(timestamp=data.get("timestamp"))
            point = {
                "measurement": data.get("name"),
                "tags": data.get("tags", {}),
                "fields": data.get("values"),
                "time": timestamp,
            }
            points_by_bucket.setdefault(bucket, []).append(point)
        try:
            for bucket, points in points_by_bucket.items():
                self._write_api.write(bucket=bucket, org=self.user, record=points)
        except Exception as exception:
            if self._is_retention_policy_violation(exception):
                logger.warning(
                    "Ignoring InfluxDB2 batch write dropped by retention policy: %s",
                    exception,
                )
                return
            logger.warning(f"Error batch writing to InfluxDB2: {exception}")
            raise TimeseriesWriteException

    def query(
        self, query: str, precision: str | None = "s", **kwargs: Any
    ) -> QueryResultSet:
        """Execute a Flux query and return ResultSet-like object for backward compatibility."""
        try:
            tables = self._query_api.query(query, org=self.user)
        except Exception as exception:
            logger.warning(f"Error querying InfluxDB2: {exception}")
            raise
        results = []
        for table in tables:
            for record in table.records:
                record_time = self._get_record_time(record)
                result = {
                    "time": self._normalize_record_time(
                        record_time, precision=precision
                    ),
                    "__raw_time": record_time,
                    "_measurement": record.values.get("_measurement"),
                    "_field": record.values.get("_field"),
                    "_value": record.get_value(),
                }
                # Add tags
                for tag_key, tag_value in record.values.items():
                    if tag_key not in FLUX_METADATA_FIELDS:
                        result[tag_key] = tag_value
                results.append(result)
        # Return wrapped ResultSet for backward compatibility with v1
        return QueryResultSet(results)

    def read(
        self,
        key: str,
        fields: FieldSelection,
        tags: TimeseriesTags | None,
        **kwargs: Any,
    ) -> list[TimeseriesPoint]:
        """Read data from InfluxDB2 using Flux query language.
        Note: InfluxDB 2.x with Flux does not support some v1 features.
        Raises NotImplementedError if unsupported parameters are used.
        """
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
                "InfluxDB 2.0 read() currently supports only single-field "
                "COUNT(DISTINCT(field)) queries."
            )
        # Build Flux query
        bucket = self._get_bucket_name(kwargs.get("retention_policy"))
        flux_query = f'from(bucket: "{bucket}")'
        # Add time range
        since = kwargs.get("since")
        if since:
            timestamp = self._format_flux_time(since)
            stop = self._format_flux_time(self._get_open_range_stop(since))
            flux_query += f" |> range(start: {timestamp}, stop: {stop})"
        else:
            flux_query += " |> range(start: -24h)"
        # Filter by measurement. InfluxDB 1.x allows comma-separated measurements.
        measurements = [
            measurement.strip() for measurement in key.split(",") if measurement.strip()
        ]
        if len(measurements) == 1:
            flux_query += (
                " |> filter(fn: (r) => "
                f"r._measurement == {self._format_flux_string(measurements[0])})"
            )
        elif measurements:
            measurement_filter = " or ".join(
                [
                    f"r._measurement == {self._format_flux_string(measurement)}"
                    for measurement in measurements
                ]
            )
            flux_query += f" |> filter(fn: (r) => {measurement_filter})"
        # Filter by tags
        if tags:
            for tag_key, tag_value in tags.items():
                flux_query += (
                    " |> filter(fn: (r) => "
                    f"{self._format_flux_property_access(tag_key)} == "
                    f"{self._format_flux_value(tag_value)})"
                )
        # Filter by fields
        if isinstance(fields, str):
            fields = [fields]
        else:
            fields = list(fields)
        extra_fields = kwargs.get("extra_fields")
        if extra_fields and extra_fields != "*":
            if isinstance(extra_fields, str):
                extra_fields = [extra_fields]
            fields.extend(extra_fields)
        elif extra_fields == "*":
            fields = ["*"]
        if fields != ["*"]:
            requested_fields = []
            seen_fields = set()
            for field in fields:
                if field not in seen_fields:
                    requested_fields.append(field)
                    seen_fields.add(field)
            for field, _op, _value in where:
                if field not in seen_fields:
                    requested_fields.append(field)
                    seen_fields.add(field)
            fields = requested_fields
        if fields != ["*"]:
            field_filter = " or ".join(
                [f"r._field == {self._format_flux_string(field)}" for field in fields]
            )
            flux_query += f" |> filter(fn: (r) => {field_filter})"
        for field, op, value in where:
            op = self._clean_operator(op)
            flux_query += (
                " |> filter(fn: (r) => "
                f"r._field == {self._format_flux_string(field)} "
                f"and r._value {op} {self._format_flux_value(value)})"
            )
        if supports_count_distinct:
            flux_query += (
                ' |> group(columns: []) |> distinct(column: "_value") |> count()'
            )
        # Apply ordering
        order = kwargs.get("order") or kwargs.get("order_by")
        if order:
            if order == "time":
                flux_query += ' |> sort(columns: ["_time"])'
            elif order == "-time":
                flux_query += ' |> sort(columns: ["_time"], desc: true)'
            else:
                raise self.client_error(
                    f'Invalid order "{order}" passed.\n'
                    'You may pass "time" / "-time" to get result sorted '
                    "in ascending /descending order respectively."
                )
        else:
            flux_query += ' |> sort(columns: ["_time"])'
        # Apply limit
        limit = kwargs.get("limit")
        if limit:
            flux_query += f" |> limit(n: {limit})"
        result = list(
            self.query(flux_query, precision=kwargs.get("precision", "s")).get_points()
        )
        if supports_count_distinct:
            return [
                {
                    "count": point.get("_value"),
                    **{
                        key: value
                        for key, value in point.items()
                        if key not in {"_measurement", "_field", "_value", "time"}
                        and key not in FLUX_METADATA_FIELDS
                    },
                    "time": point.get("time"),
                }
                for point in result
            ]
        return self._normalize_read_points(result)

    def _normalize_read_points(self, points, include_tags=True):
        normalized = {}
        special_fields = {"_measurement", "_field", "_value", "time", "__raw_time"}
        for point in points:
            field = point.get("_field")
            if not field:
                continue
            tags = {}
            if include_tags:
                tags = {
                    key: value
                    for key, value in point.items()
                    if key not in special_fields and key not in FLUX_METADATA_FIELDS
                }
            key = (
                point.get("__raw_time", point.get("time")),
                tuple(sorted(tags.items())),
            )
            normalized.setdefault(key, {"time": point.get("time"), **tags})
            existing_value = normalized[key].get(field)
            point_value = point.get("_value")
            if (
                not include_tags
                and existing_value is not None
                and isinstance(existing_value, (int, float))
                and isinstance(point_value, (int, float))
            ):
                normalized[key][field] = existing_value + point_value
            else:
                normalized[key][field] = point_value
        return list(normalized.values())

    def _extract_expected_fields(self, query):
        expected_fields = []

        def add_field(field):
            if field and field not in expected_fields:
                expected_fields.append(field)

        has_field_remap = "_field:" in query
        if has_field_remap:
            for match in re.findall(r'_field:\s*"([^"]+)"', query):
                add_field(match)
            for match in re.findall(r'then\s*"([^"]+)"', query):
                add_field(match)
            for match in re.findall(r'else\s*"([^"]+)"', query):
                add_field(match)
            return expected_fields

        for match in re.findall(r'r\._field == "([^"]+)"', query):
            add_field(match)

        field_in_match = re.search(r"r\._field in \(([^)]+)\)", query)
        if field_in_match:
            for match in re.findall(r'"([^"]+)"', field_in_match.group(1)):
                add_field(match)

        field_regex_match = re.search(r"r\._field =~ /\^\(([^)]+)\)\$/", query)
        if field_regex_match:
            for match in field_regex_match.group(1).split("|"):
                add_field(match)

        return expected_fields

    def _backfill_expected_fields(self, points, query):
        expected_fields = self._extract_expected_fields(query)
        if not expected_fields:
            return points
        for point in points:
            for field in expected_fields:
                point.setdefault(field, None)
        return points

    def _build_delete_predicate(
        self, key: str | None = None, tags: TimeseriesTags | None = None
    ) -> str:
        predicates = []
        if key:
            predicates.append(f"_measurement={self._format_flux_string(key)}")
        if tags:
            for tag_key, tag_value in tags.items():
                self._validate_delete_predicate_key(tag_key)
                predicates.append(f"{tag_key}={self._format_flux_string(tag_value)}")
        return " AND ".join(predicates)

    @retry
    def _delete_range(self, predicate: str = "", bucket: str | None = None) -> None:
        start = datetime(1970, 1, 1, tzinfo=timezone.utc)
        stop = datetime.now(timezone.utc)
        self._delete_api.delete(
            start,
            stop,
            predicate,
            bucket=bucket or self.db_name,
            org=self.user,
        )

    @retry
    def delete_series(
        self, key: str | None = None, tags: TimeseriesTags | None = None
    ) -> None:
        """
        Backward-compatible InfluxDB 1.8 style series deletion.
        In InfluxDB 2.0 this is implemented as a predicate-based delete over
        the full time range of the bucket.
        """
        predicate = self._build_delete_predicate(key=key, tags=tags)
        if not predicate:
            raise ValueError("delete_series requires at least one of key or tags")
        for bucket in self._get_known_bucket_names():
            self._delete_range(predicate, bucket=bucket)

    def delete_metric_data(
        self, key: str | None = None, tags: TimeseriesTags | None = None
    ) -> None:
        """Deletes metric data based on measurement and tags."""
        predicate = self._build_delete_predicate(key=key, tags=tags)
        if not predicate:
            self._reset_known_buckets()
            logger.debug("Reset InfluxDB2 buckets for full metric data cleanup")
            return
        for bucket in self._get_known_bucket_names():
            self._delete_range(predicate, bucket=bucket)
        logger.debug(f"Deleted metric data: key={key}, tags={tags}")

    def _reset_known_buckets(self):
        api = self.db.buckets_api()
        for bucket_name in self._get_known_bucket_names():
            bucket = api.find_bucket_by_name(bucket_name)
            if not bucket:
                self._ensure_bucket_exists(bucket_name)
                continue
            retention_rules = bucket.retention_rules
            api.delete_bucket(bucket)
            create_kwargs = {
                "bucket_name": bucket_name,
                "org": self.user,
            }
            if retention_rules:
                create_kwargs["retention_rules"] = retention_rules
            api.create_bucket(**create_kwargs)

    def get_list_query(self, query: str, precision: str = "s") -> list[TimeseriesPoint]:
        """Execute a query and flatten GROUP BY TAG results for chart rendering.
        Mimics InfluxDB 1.x behavior for queries containing GROUP BY TAG clauses.
        Flattens tagged results into a time-indexed dictionary structure for UI charts.
        Args:
            query (str): Flux query string to execute
            precision (str): Timestamp precision (ignored in v2, kept for compatibility)
        Returns:
            list: List of point dictionaries with time-indexed values, sorted by time
        """
        # Execute the query and get QueryResultSet wrapper
        result = self.query(query, precision=precision)
        # Ordinary chart reads should ignore object/interface tags and just
        # return field values. Only keep the group-by-tag path when the Flux
        # query explicitly groups by columns.
        if (
            "group(columns:" not in query
            or not result.keys()
            or result.keys()[0][1] is None
        ):
            points = self._normalize_read_points(
                list(result.get_points()), include_tags=False
            )
            return self._backfill_expected_fields(points, query)
        # Handle queries with GROUP BY TAG clause
        # Group results by time and merge tag-specific values into single record
        result_points = {}
        for (measurement, tags), group_points in result.items():
            # Create tag suffix by joining tag values with underscore
            # This creates a unique identifier for each tag combination
            tag_suffix = "_".join(str(v) for v in tags.values())
            # Process each point in this tag group
            for point in group_points:
                point_time = point.get("time")
                if not point_time:
                    continue
                values = {
                    "time": point_time,
                    tag_suffix: point.get("_value"),
                }
                # Merge into result dictionary (keyed by time)
                # If time already exists, update with new tag values
                if point_time in result_points:
                    result_points[point_time].update(values)
                else:
                    result_points[point_time] = values
        # Return sorted by time (ascending)
        points = sorted(result_points.values(), key=lambda p: p.get("time", ""))
        return points

    @retry
    def get_list_retention_policies(self) -> list[TimeseriesPoint]:
        """Returns v1-compatible retention policy records for known buckets."""
        try:
            api = self.db.buckets_api()
            policies = []
            for bucket_name in self._get_known_bucket_names():
                bucket = api.find_bucket_by_name(bucket_name)
                if not bucket:
                    continue
                policy_name = self._get_retention_policy_name(bucket_name)
                policies.append(
                    {
                        "name": policy_name,
                        "default": policy_name == "autogen",
                        "duration": self._get_bucket_retention_duration(bucket),
                        "replication": 1,
                    }
                )
            return policies
        except self.client_error:
            return []

    def _build_chart_base_query(
        self, params: ChartQueryParams, time: Any, group_map: Mapping[Any, str]
    ) -> str:
        flux_query = f'from(bucket: "{self.db_name}")'
        start_range = params.get("time")
        if start_range:
            start_range = self._normalize_chart_start_range(start_range)
        else:
            time_val = self._normalize_chart_window(time)
            start_range = f"-{time_val}"
        if params.get("end_date"):
            end_range = self._format_flux_time(params["end_date"])
            flux_query += f" |> range(start: {start_range}, stop: {end_range})"
        else:
            flux_query += f" |> range(start: {start_range})"
        measurement = params.get("key")
        if measurement:
            flux_query += (
                " |> filter(fn: (r) => "
                f"r._measurement == {self._format_flux_string(measurement)})"
            )
        if params.get("content_type") and params.get("object_id"):
            content_type = params["content_type"]
            object_id = params["object_id"]
            flux_query += (
                " |> filter(fn: (r) => "
                f"r.content_type == {self._format_flux_string(content_type)} "
                f"and r.object_id == {self._format_flux_string(object_id)})"
            )
        if params.get("ifname"):
            ifname = params["ifname"]
            flux_query += (
                " |> filter(fn: (r) => "
                f"r.ifname == {self._format_flux_string(ifname)})"
            )
        flux_query += self._format_filter(
            "organization_id", params.get("organization_id")
        )
        flux_query += self._format_filter("location_id", params.get("location_id"))
        flux_query += self._format_filter("floorplan_id", params.get("floorplan_id"))
        return flux_query

    def _format_filter(self, field, value):
        if value in (None, "", "__all__"):
            return ""
        if isinstance(value, (list, tuple)):
            items = [item for item in value if item != "__all__"]
            if not items:
                return ""
            values = ", ".join([self._format_flux_string(item) for item in items])
            return f" |> filter(fn: (r) => contains(value: r.{field}, set: [{values}]))"
        return (
            " |> filter(fn: (r) => " f"r.{field} == {self._format_flux_string(value)})"
        )

    def _format_field_filter(self, fields, field_name):
        if fields:
            field_list = ", ".join(
                [self._format_flux_string(field) for field in fields]
            )
            return (
                " |> filter(fn: (r) => "
                f"contains(value: r._field, set: [{field_list}]))"
            )
        if field_name:
            return (
                " |> filter(fn: (r) => "
                f"r._field == {self._format_flux_string(field_name)})"
            )
        return ""

    def _format_chart_query(self, query, params, time, group_map, summary, fields):
        start_range = params.get("time")
        if start_range:
            time_start = self._normalize_chart_start_range(start_range)
        else:
            time_val = self._normalize_chart_window(time)
            time_start = f"-{time_val}"
        end_range = ""
        if params.get("end_date"):
            end_range = f', stop: {self._format_flux_time(params["end_date"])}'
        window = self._normalize_chart_window(time, group_map)
        formatted = query.format(
            bucket=self.db_name,
            key=self._escape_flux_string(params.get("key", "")),
            time_start=time_start,
            end_range=end_range,
            window=window,
            field_name=self._escape_flux_string(params.get("field_name", "")),
            content_type=self._escape_flux_string(params.get("content_type", "")),
            object_id=self._escape_flux_string(params.get("object_id", "")),
            ifname=self._escape_flux_string(params.get("ifname", "")),
            organization_id=self._escape_flux_string(params.get("organization_id", "")),
            location_id=self._escape_flux_string(params.get("location_id", "")),
            floorplan_id=self._escape_flux_string(params.get("floorplan_id", "")),
            content_type_filter=self._format_filter(
                "content_type", params.get("content_type")
            ),
            object_id_filter=self._format_filter("object_id", params.get("object_id")),
            ifname_filter=self._format_filter("ifname", params.get("ifname")),
            organization_id_filter=self._format_filter(
                "organization_id", params.get("organization_id")
            ),
            location_id_filter=self._format_filter(
                "location_id", params.get("location_id")
            ),
            floorplan_id_filter=self._format_filter(
                "floorplan_id", params.get("floorplan_id")
            ),
            field_filter=self._format_field_filter(
                fields, params.get("field_name", "")
            ),
        )
        if summary:
            formatted = re.sub(
                r"\s\|> window\(every: [^)]+\)\s*"
                r'\|> unique\(column: "_value"\)\s*'
                r"\|> count\(\)\s*"
                r'\|> duplicate\(column: "_start", as: "_time"\)',
                ' |> unique(column: "_value") |> count()',
                formatted,
            )

            def replace_summary_window(match):
                aggregate_fn = match.group(1)
                if aggregate_fn == "mode":
                    return " |> last()"
                return f" |> {aggregate_fn}()"

            formatted = re.sub(
                r"\s\|> aggregateWindow\(every: [^,]+, fn: (\w+)(?:, [^)]+)?\)"
                r"(?:\s*\|> map\(fn: \(r\) => \(\{r with _time: "
                r"date\.truncate\(t: r\._time, unit: [^)]+\)\}\)\))?",
                replace_summary_window,
                formatted,
            )
        return formatted

    def _get_top_fields(
        self,
        query: str | None,
        params: ChartQueryParams,
        chart_type: str,
        group_map: Mapping[Any, str],
        number: int,
        time: Any,
        timezone: str = settings.TIME_ZONE,
    ) -> list[str]:
        if number <= 0:
            return []
        ranking_params = params.copy()
        ranking_params["field_name"] = ""
        flux_query = self.get_query(
            chart_type=chart_type,
            params=ranking_params,
            time=time,
            group_map=group_map,
            summary=True,
            query=query,
            timezone=timezone,
        )
        flux_query += ' |> group(columns: ["_field"]) |> sum()'
        result = list(self.query(flux_query).get_points())
        result.sort(key=lambda point: point.get("_value", 0), reverse=True)
        return [point["_field"] for point in result[:number] if point.get("_field")]

    def get_query(
        self,
        chart_type: str,
        params: ChartQueryParams,
        time: Any,
        group_map: Mapping[Any, str],
        summary: bool = False,
        fields: Sequence[str] | None = None,
        query: str | None = None,
        timezone: str | None = settings.TIME_ZONE,
    ) -> str:
        """Build Flux query for chart rendering with full parameter consumption.
        Consumes all required params to filter data correctly:
        - content_type, object_id: Device-specific queries
        - ifname: Interface-specific queries
        - organization_id, location_id, floorplan_id: Organization-level queries
        - field_name: Field to query
        - end_date: End time for range
        Supports chart_type: uptime, packet_loss, rtt, wifi_clients,
                             general_wifi_clients, traffic, general_traffic
        """
        if query:
            return self._format_chart_query(
                query, params, time, group_map, summary, fields
            )
        flux_query = self._build_chart_base_query(params, time, group_map)
        # 8. FIELD NAME FILTER: Use field_name from params if not overridden by fields
        if not fields and params.get("field_name"):
            field_name = params["field_name"]
            flux_query += (
                " |> filter(fn: (r) => "
                f"r._field == {self._format_flux_string(field_name)})"
            )
        # 9. EXPLICIT FIELDS FILTER: Use fields parameter if provided
        if fields:
            field_list = ", ".join(
                [self._format_flux_string(field) for field in fields]
            )
            flux_query += (
                " |> filter(fn: (r) => "
                f"contains(value: r._field, set: [{field_list}]))"
            )
        # 10. CHART TYPE SPECIFIC AGGREGATIONS AND TRANSFORMATIONS
        if chart_type == "wifi_clients":
            # WiFi clients: COUNT(DISTINCT) simulation with distinct() + count()
            flux_query += ' |> distinct(column: "_value") |> count()'
        elif chart_type == "general_wifi_clients":
            # General WiFi clients: COUNT(DISTINCT) at org level
            flux_query += ' |> distinct(column: "_value") |> count()'
        elif chart_type == "traffic":
            # Traffic: Convert bytes to GB (divide by 1e9)
            flux_query += (
                " |> sum() |> map(fn: (r) => ({r with "
                "_value: float(v: r._value) / 1000000000.0}))"
            )
        elif chart_type == "general_traffic":
            # General traffic: Convert bytes to GB at org level
            flux_query += (
                " |> sum() |> map(fn: (r) => ({r with "
                "_value: float(v: r._value) / 1000000000.0}))"
            )
        elif chart_type == "rtt":
            # RTT: Multiple aggregations (mean of mean, max, min)
            flux_query += " |> mean()"
        else:
            # Default handling: uptime, packet_loss, etc.
            if summary:
                flux_query += " |> mean()"
        return flux_query
