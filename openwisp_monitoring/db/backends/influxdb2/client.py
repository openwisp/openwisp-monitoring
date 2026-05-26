import logging
import re
from datetime import datetime, timezone

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from openwisp_monitoring.utils import retry

from ...exceptions import TimeseriesWriteException
from .. import TIMESERIES_DB

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


class QueryResultSet:
    """
    Wrapper to mimic InfluxDB 1.x ResultSet behavior for InfluxDB 2.x responses.
    This ensures backward compatibility with existing code that expects
    ResultSet objects with get_points() and keys() methods.
    v1 groups results by (measurement, tags) pairs. This implementation
    mimics that structure for backward compatibility.
    """

    def __init__(self, points):
        """
        Initialize with a list of point dictionaries from InfluxDB 2.7
        Args:
            points: List of data point dictionaries with structure:
                   {"_measurement": str, "_field": str, "_value": any,
                    "time": datetime, ...other_tags}
        """
        self.points = points
        self._series_cache = None

    def _group_by_measurement_tags(self):
        """
        Group points by (measurement, tags) to mimic v1 structure.
        Returns a dict: {(measurement, frozenset(tags.items())): [points]}
        """
        if self._series_cache is not None:
            return self._series_cache
        series_dict = {}

        for point in self.points:
            measurement = point.get("_measurement", "results")
            # Extract tags (all keys except special fields)
            special_fields = {"_measurement", "_field", "_value", "time"}
            tags = {}
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

    def get_points(self, measurement=None, tags=None):
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

    def keys(self):
        """
        Return list of (measurement, tags) tuples.
        Mimics v1 ResultSet.keys() which returns list of
        (measurement_name, tags_dict) tuples.
        """
        series_dict = self._group_by_measurement_tags()
        keys = []
        for measurement, tags_frozen in series_dict.keys():
            tags_dict = dict(tags_frozen) if tags_frozen else None
            keys.append((measurement, tags_dict))
        return keys

    def items(self):
        """
        Return list of (key, points_generator) tuples.
        Mimics v1 ResultSet.items().
        """
        series_dict = self._group_by_measurement_tags()
        items = []

        for (measurement, tags_frozen), points in series_dict.items():
            tags_dict = dict(tags_frozen) if tags_frozen else None
            key = (measurement, tags_dict)
            # Create generator from points
            points_gen = (point for point in points)
            items.append((key, points_gen))
        return items

    @staticmethod
    def _tag_matches(series_tags, filter_tags):
        """Check if all key/values in filter match in tags."""
        for tag_name, tag_value in filter_tags.items():
            if series_tags.get(tag_name) != tag_value:
                return False
        return True

    def __iter__(self):
        """Yield points like v1 ResultSet."""
        for _key in self.keys():
            for point in self.get_points():
                yield point

    def __len__(self):
        """Return the number of series (measurement, tags) combinations."""
        return len(self.keys())

    def __repr__(self):
        """Representation of ResultSet object."""
        items = []
        for key, points in self.items():
            items.append("'%s': %s" % (key, list(points)))
        return "ResultSet({%s})" % ", ".join(items)


class DatabaseClient(object):
    """InfluxDB 2.x client for timeseries database operations."""

    _AGGREGATE = ["mean", "sum", "count", "max", "min", "stddev"]
    backend_name = "influxdb2"
    _FORBIDDEN = ["drop", "delete", "alter", "create", "into"]

    def __init__(self, db_name=None):
        """Initialize InfluxDB 2 client.

        Args:
            db_name: Bucket name (equivalent to database in InfluxDB 1.x)
        """
        self._db = None
        self.db_name = db_name or TIMESERIES_DB["NAME"]
        self.org = TIMESERIES_DB.get("ORG", "openwisp")
        self.token = TIMESERIES_DB.get("TOKEN", "")
        try:
            from influxdb_client import InfluxDBClient
            from influxdb_client.client.exceptions import InfluxDBError

            self.InfluxDBClient = InfluxDBClient
            self.client_error = InfluxDBError
        except ImportError:
            raise ImportError(
                "influxdb-client is required for InfluxDB 2.x support. "
                "Install it with: pip install influxdb-client"
            )

    @retry
    def create_database(self):
        """Creates bucket if necessary."""
        api = self.db.buckets_api()
        try:
            bucket = api.find_bucket_by_name(self.db_name)
            if bucket:
                logger.debug(f'InfluxDB2 bucket "{self.db_name}" already exists')
                return
        except self.client_error:
            pass
        api.create_bucket(bucket_name=self.db_name, org=self.org)
        logger.debug(f'Created InfluxDB2 bucket "{self.db_name}"')

    @retry
    def drop_database(self):
        """Drops bucket if it exists."""
        api = self.db.buckets_api()
        try:
            bucket = api.find_bucket_by_name(self.db_name)
            if bucket:
                api.delete_bucket(bucket)
                logger.debug(f'Dropped InfluxDB2 bucket "{self.db_name}"')
        except self.client_error:
            logger.debug(f'InfluxDB2 bucket "{self.db_name}" not found')

    @cached_property
    def db(self):
        """Returns an InfluxDBClient instance."""
        url = (
            TIMESERIES_DB.get("URL")
            or f"http://{TIMESERIES_DB['HOST']}:{TIMESERIES_DB['PORT']}"
        )
        return self.InfluxDBClient(url=url, token=self.token, org=self.org)

    @cached_property
    def _write_api(self):
        """Returns write API instance."""
        from influxdb_client.client.write_api import (  # docs https://influxdb-client.readthedocs.io/en/stable/api.html#influxdb_client.WriteApi
            SYNCHRONOUS,
        )

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
    def use_udp(self):
        return False

    @retry
    def create_or_alter_retention_policy(self, name, duration):
        """Creates or alters retention policy on a bucket."""
        from influxdb_client.domain import BucketRetentionRules

        if name != "autogen":
            logger.warning(
                f'InfluxDB 2.x manages retention at bucket level; ignoring "{name}"'
            )
            return
        api = self.db.buckets_api()
        try:
            bucket = api.find_bucket_by_name(self.db_name)
        except self.client_error:
            logger.warning(f'Bucket "{self.db_name}" not found. Create database first.')
            return
        duration_seconds = self._duration_to_seconds(duration)
        bucket.retention_rules = [
            BucketRetentionRules(type="expire", every_seconds=duration_seconds)
        ]

        try:
            api.update_bucket(bucket=bucket)
        except self.client_error as exception:
            logger.warning(f"Could not update InfluxDB2 bucket retention: {exception}")
            return
        logger.debug(
            f'Created/updated InfluxDB2 retention policy "{name}" with duration {duration}'
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

    def validate_query(self, query):
        for word in self._FORBIDDEN:
            if word in query.lower():
                msg = _(f'the word "{word.upper()}" is not allowed')
                raise ValidationError({"configuration": msg})
        return self._is_aggregate(query)

    def _is_aggregate(self, query):
        query = query.lower()
        return any(f"{word}(" in query for word in self._AGGREGATE)

    def write(self, name, values, **kwargs):
        timestamp = self._get_timestamp(timestamp=kwargs.get("timestamp"))
        # Log ignored v1 options because v2 manages these at bucket level.
        if kwargs.get("database") and kwargs.get("database") != self.db_name:
            logger.warning(
                f'Parameter "database" is ignored in InfluxDB 2.x. '
                f'Using bucket "{self.db_name}"'
            )
        if kwargs.get("retention_policy"):
            logger.warning(
                'Parameter "retention_policy" is managed at bucket level in InfluxDB 2.x'
            )
        point = {
            "measurement": name,
            "tags": kwargs.get("tags", {}),
            "fields": values,
            "time": timestamp,
        }
        try:
            self._write_api.write(
                bucket=self.db_name,
                org=self.org,
                record=point,
            )
        except Exception as exception:
            logger.warning(f"Error writing to InfluxDB2: {exception}")
            raise TimeseriesWriteException

    def batch_write(self, metric_data):
        """Write multiple data points in batch."""
        for data in metric_data:
            if data.get("database") and data.get("database") != self.db_name:
                logger.warning(
                    f'Parameter "database" is ignored in InfluxDB 2.7'
                    f'Writing to bucket "{self.db_name}"'
                )
            if data.get("retention_policy"):
                logger.warning(
                    'Parameter "retention_policy" is managed at bucket level in InfluxDB 2.x. '
                    "All data uses bucket retention policy."
                )
        points = []
        for data in metric_data:
            timestamp = self._get_timestamp(timestamp=data.get("timestamp"))
            point = {
                "measurement": data.get("name"),
                "tags": data.get("tags", {}),
                "fields": data.get("values"),
                "time": timestamp,
            }
            points.append(point)
        try:
            self._write_api.write(bucket=self.db_name, org=self.org, record=points)
        except Exception as exception:
            logger.warning(f"Error batch writing to InfluxDB2: {exception}")
            raise TimeseriesWriteException

    def query(self, query, **kwargs):
        """Execute a Flux query and return ResultSet-like object for backward compatibility."""
        try:
            tables = self._query_api.query(query, org=self.org)
            results = []
            for table in tables:
                for record in table.records:
                    result = {
                        "time": record.get_time(),
                        "_measurement": record.get_measurement(),
                        "_field": record.get_field(),
                        "_value": record.get_value(),
                    }
                    # Add tags
                    for tag_key, tag_value in record.values.items():
                        if tag_key not in FLUX_METADATA_FIELDS:
                            result[tag_key] = tag_value
                    results.append(result)
            # Return wrapped ResultSet for backward compatibility with v1
            return QueryResultSet(results)
        except Exception as exception:
            logger.warning(f"Error querying InfluxDB2: {exception}")
            raise

    def read(self, key, fields, tags, **kwargs):
        """Read data from InfluxDB2 using Flux query language.
        Note: InfluxDB 2.x with Flux does not support some v1 features.
        Raises NotImplementedError if unsupported parameters are used.
        """
        # Check for unsupported parameters and raise explicit errors
        unsupported_params = {
            "extra_fields": "Flux requires explicit field selection instead of wildcard expansion",
            "distinct_fields": "Use COUNT(DISTINCT) in Flux or custom queries",
            "count_fields": "Use COUNT aggregation in Flux or custom queries",
            "retention_policy": "InfluxDB 2.x uses buckets instead of retention policies",
            "where": "Use custom Flux query instead of WHERE clause shortcuts",
            "precision": "InfluxDB 2.x uses ISO8601 timestamps; precision parameter not supported",
        }
        for param, reason in unsupported_params.items():
            if param in kwargs:
                raise NotImplementedError(
                    f"InfluxDB 2.x read() does not support '{param}' parameter. "
                    f"Reason: {reason}. "
                    f"For complex queries, use timeseries_db.query() with custom Flux instead."
                )
        # Build Flux query
        flux_query = f'from(bucket: "{self.db_name}")'
        # Add time range
        since = kwargs.get("since")
        if since:
            timestamp = self._get_timestamp(since)
            flux_query += f" |> range(start: {timestamp})"
        else:
            flux_query += " |> range(start: -24h)"
        # Filter by measurement
        flux_query += f' |> filter(fn: (r) => r._measurement == "{key}")'
        # Filter by tags
        if tags:
            for tag_key, tag_value in tags.items():
                flux_query += f' |> filter(fn: (r) => r.{tag_key} == "{tag_value}")'
        # Filter by fields
        if isinstance(fields, str):
            fields = [fields]
        field_filter = " or ".join([f'r._field == "{field}"' for field in fields])
        flux_query += f" |> filter(fn: (r) => {field_filter})"
        # Apply ordering
        order = kwargs.get("order")
        if order:
            if order == "time":
                flux_query += ' |> sort(columns: ["_time"])'
            elif order == "-time":
                flux_query += ' |> sort(columns: ["_time"], desc: true)'
        # Apply limit
        limit = kwargs.get("limit")
        if limit:
            flux_query += f" |> limit(n: {limit})"
        return self._normalize_read_points(list(self.query(flux_query).get_points()))

    def _normalize_read_points(self, points):
        normalized = {}
        special_fields = {"_measurement", "_field", "_value", "time"}
        for point in points:
            field = point.get("_field")
            if not field:
                continue
            tags = {
                key: value
                for key, value in point.items()
                if key not in special_fields and key not in FLUX_METADATA_FIELDS
            }
            key = (point.get("time"), tuple(sorted(tags.items())))
            normalized.setdefault(key, {"time": point.get("time"), **tags})
            normalized[key][field] = point.get("_value")
        return list(normalized.values())

    def delete_metric_data(self, key=None, tags=None):
        """Deletes metric data based on measurement and tags."""
        try:
            # Delete from epoch to now
            start = datetime(1970, 1, 1, tzinfo=timezone.utc)
            stop = datetime.now(timezone.utc)
            # Build predicates for deletion
            predicates = []
            if key:
                predicates.append(f'_measurement="{key}"')
            if tags:
                for tag_key, tag_value in tags.items():
                    predicates.append(f'{tag_key}="{tag_value}"')
            predicate = " AND ".join(predicates) if predicates else ""
            self._delete_api.delete(
                start,
                stop,
                predicate,
                bucket=self.db_name,
                org=self.org,
            )
            logger.debug(f"Deleted metric data: key={key}, tags={tags}")
        except Exception as exception:
            logger.warning(f"Error deleting metric data: {exception}")

    def get_list_query(self, query, precision="s"):
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
        result = self.query(query)
        # If no results or no tag grouping, return flattened points as-is
        if not result.keys() or result.keys()[0][1] is None:
            return list(result.get_points())
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
                # Extract non-time values and prefix with tag suffix
                # This allows multiple tags to coexist in the same time bucket
                values = {}
                for key, value in point.items():
                    if key != "time":
                        # Create field with tag suffix to avoid collisions
                        values[tag_suffix] = value
                values["time"] = point_time
                # Merge into result dictionary (keyed by time)
                # If time already exists, update with new tag values
                if point_time in result_points:
                    result_points[point_time].update(values)
                else:
                    result_points[point_time] = values
        # Return sorted by time (ascending)
        return sorted(result_points.values(), key=lambda p: p.get("time", ""))

    @retry
    def get_list_retention_policies(self):
        """Returns list of retention policies for the bucket."""
        try:
            api = self.db.buckets_api()
            bucket = api.find_bucket_by_name(self.db_name)
            policies = []
            if bucket.retention_rules:
                for rule in bucket.retention_rules:
                    policies.append(
                        {
                            "name": "default",
                            "duration": f"{rule.every_seconds}s",
                            "replication": 1,
                        }
                    )
            return policies
        except self.client_error:
            return []

    def get_query(
        self,
        chart_type,
        params,
        time,
        group_map,
        summary=False,
        fields=None,
        query=None,
        timezone=settings.TIME_ZONE,
    ):
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
        flux_query = f'from(bucket: "{self.db_name}")'
        # 1. TIME RANGE: Use params for start and end dates
        time_val = group_map.get(time, "1h") if group_map else "1h"
        start_range = f"-{time_val}"
        # Check for custom end_date from params
        if params.get("end_date"):
            end_range = params["end_date"]
            flux_query += f" |> range(start: {start_range}, stop: {end_range})"
        else:
            flux_query += f" |> range(start: {start_range})"
        # 2. MEASUREMENT FILTER: Use params["key"]
        measurement = params.get("key")
        if measurement:
            flux_query += f' |> filter(fn: (r) => r._measurement == "{measurement}")'
        # 3. DEVICE-SPECIFIC FILTERS: Use content_type + object_id
        if params.get("content_type") and params.get("object_id"):
            content_type = params["content_type"]
            object_id = params["object_id"]
            flux_query += (
                f' |> filter(fn: (r) => r.content_type == "{content_type}" '
                f'and r.object_id == "{object_id}")'
            )
        # 4. INTERFACE FILTER: Use ifname from params
        if params.get("ifname"):
            ifname = params["ifname"]
            flux_query += f' |> filter(fn: (r) => r.ifname == "{ifname}")'
        # 5. ORGANIZATION FILTER: Use organization_id from params
        if params.get("organization_id"):
            org_id = params["organization_id"]
            # Handle list format (e.g., ["org1"] or "__all__")
            if isinstance(org_id, list):
                org_id = org_id[0]
            if org_id != "__all__":
                flux_query += f' |> filter(fn: (r) => r.organization_id == "{org_id}")'
        # 6. LOCATION FILTER - Use location_id from params
        if params.get("location_id"):
            location_id = params["location_id"]
            flux_query += f' |> filter(fn: (r) => r.location_id == "{location_id}")'
        # 7. FLOORPLAN FILTER - Use floorplan_id from params
        if params.get("floorplan_id"):
            floorplan_id = params["floorplan_id"]
            flux_query += f' |> filter(fn: (r) => r.floorplan_id == "{floorplan_id}")'
        # 8. FIELD NAME FILTER: Use field_name from params if not overridden by fields
        if not fields and params.get("field_name"):
            field_name = params["field_name"]
            flux_query += f' |> filter(fn: (r) => r._field == "{field_name}")'
        # 9. EXPLICIT FIELDS FILTER: Use fields parameter if provided
        if fields:
            field_list = ", ".join([f'"{f}"' for f in fields])
            flux_query += f" |> filter(fn: (r) => r._field in ({field_list}))"
        # 10. CHART TYPE SPECIFIC AGGREGATIONS AND TRANSFORMATIONS
        if chart_type == "wifi_clients":
            # WiFi clients: COUNT(DISTINCT) simulation with distinct() + count()
            flux_query += ' |> distinct(column: "clients") |> count()'
        elif chart_type == "general_wifi_clients":
            # General WiFi clients: COUNT(DISTINCT) at org level
            flux_query += ' |> distinct(column: "clients") |> count()'
        elif chart_type == "traffic":
            # Traffic: Convert bytes to GB (divide by 1e9)
            flux_query += (
                " |> sum() |> map(fn: (r) => ({r with _value: r._value / 1000000000}))"
            )
        elif chart_type == "general_traffic":
            # General traffic: Convert bytes to GB at org level
            flux_query += (
                " |> sum() |> map(fn: (r) => ({r with _value: r._value / 1000000000}))"
            )
        elif chart_type == "rtt":
            # RTT: Multiple aggregations (mean of mean, max, min)
            flux_query += " |> mean()"
        else:
            # Default handling: uptime, packet_loss, etc.
            if summary:
                flux_query += " |> mean()"
        return flux_query
