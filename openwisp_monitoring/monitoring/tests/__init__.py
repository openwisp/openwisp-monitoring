import os
import time
from datetime import timedelta
from unittest import SkipTest

from django.core.cache import cache
from django.utils.timezone import now
from swapper import load_model

from openwisp_users.tests.utils import TestOrganizationMixin

from ...db import timeseries_db
from ...db.backends import TIMESERIES_DB
from ...device.utils import manage_short_retention_policy
from ..configuration import (
    DEFAULT_CHARTS,
    DEFAULT_METRICS,
    register_chart,
    register_metric,
    unregister_chart,
    unregister_metric,
)

start_time = now()
ten_minutes_ago = start_time - timedelta(minutes=10)
Chart = load_model("monitoring", "Chart")
Metric = load_model("monitoring", "Metric")
AlertSettings = load_model("monitoring", "AlertSettings")

default_message = (
    "{notification.actor.name} for device [{notification.target}]"
    "({notification.target_link}) {notification.verb}."
)

test_notification = {
    "problem": {
        "verbose_name": "Monitoring Alert",
        "verb": "crossed the threshold",
        "level": "warning",
        "email_subject": "[{site.name}] PROBLEM: {notification.actor.name} {notification.target}",
        "message": default_message,
    },
    "recovery": {
        "verbose_name": "Monitoring Alert",
        "verb": "returned within the threshold",
        "level": "info",
        "email_subject": "[{site.name}] RECOVERY: {notification.actor.name} {notification.target}",
        "message": default_message,
    },
}


class RequireTimeseriesBackendMixin:
    expected_backend = None
    default_backend = "influxdb"

    @classmethod
    def _require_timeseries_backend(cls):
        if (
            os.environ.get("TIMESERIES_BACKEND", cls.default_backend)
            != cls.expected_backend
        ):
            raise SkipTest(
                f'Set TIMESERIES_BACKEND="{cls.expected_backend}" to run these tests.'
            )

    @classmethod
    def setUpClass(cls):
        cls._require_timeseries_backend()
        super().setUpClass()


# these custom metric configurations are used for automated testing purposes
metrics = {
    "test_metric": {
        "name": "dummy",
        "key": "{key}",
        "field_name": "{field_name}",
        "label": "Test Metric",
        "notification": test_notification,
    },
    "test_alert_field": {
        "name": "test_alert_related",
        "key": "{key}",
        "field_name": "test_alert_field",
        "label": "Test alert related",
        "notification": test_notification,
        "related_fields": ["test_related_1", "test_related_2", "test_related_3"],
        "alert_field": "test_related_2",
    },
    "top_fields_mean": {
        "name": "top_fields_mean_test",
        "key": "{key}",
        "field_name": "{field_name}",
        "label": "top fields mean test",
        "related_fields": ["google", "facebook", "reddit"],
    },
    "get_top_fields": {
        "name": "get_top_fields_test",
        "key": "{key}",
        "field_name": "{field_name}",
        "label": "get top fields test",
        "related_fields": ["http2", "ssh", "udp", "spdy"],
    },
}

# this custom chart configuration is used for automated testing purposes
charts = {
    "histogram": {
        "type": "histogram",
        "title": "Histogram",
        "description": "Histogram",
        "top_fields": 2,
        "order": 999,
        "query": {
            "influxdb": (
                "SELECT {fields|SUM|/ 1} FROM {key} "
                "WHERE time >= '{time}' AND content_type = "
                "'{content_type}' AND object_id = '{object_id}'"
            ),
            "influxdb2": (
                'from(bucket: "{bucket}") |> range(start: {time_start}) '
                '|> filter(fn: (r) => r._measurement == "{key}")'
                "{content_type_filter}{object_id_filter}{field_filter}"
                " |> sum()"
                " |> map(fn: (r) => ({{r with _value: float(v: r._value)}}))"
            ),
        },
    },
    "dummy": {
        "type": "line",
        "title": "Dummy chart",
        "description": "Dummy chart for testing purposes.",
        "unit": "candies",
        "order": 999,
        "query": None,
    },
    "bad_test": {
        "type": "line",
        "title": "Bugged chart for testing purposes",
        "description": "Bugged chart for testing purposes.",
        "unit": "bugs",
        "order": 999,
        "query": {"influxdb": "BAD", "influxdb2": "BAD"},
    },
    "default": {
        "type": "line",
        "title": "Default query for testing purposes",
        "description": "Default query for testing purposes",
        "unit": "n.",
        "order": 999,
        "query": {
            "influxdb": (
                "SELECT {field_name} FROM {key} WHERE time >= '{time}' AND "
                "content_type = '{content_type}' AND object_id = '{object_id}'"
            ),
            "influxdb2": (
                'from(bucket: "{bucket}") |> range(start: {time_start}) '
                '|> filter(fn: (r) => r._measurement == "{key}")'
                "{content_type_filter}{object_id_filter}{field_filter}"
            ),
        },
    },
    "multiple_test": {
        "type": "line",
        "title": "Multiple test",
        "description": "For testing purposes",
        "unit": "n.",
        "order": 999,
        "query": {
            "influxdb": (
                "SELECT {field_name}, value2 FROM {key} WHERE time >= '{time}' AND "
                "content_type = '{content_type}' AND object_id = '{object_id}'"
            ),
            "influxdb2": (
                'from(bucket: "{bucket}") |> range(start: {time_start}) '
                '|> filter(fn: (r) => r._measurement == "{key}")'
                "{content_type_filter}{object_id_filter}"
                ' |> filter(fn: (r) => r._field == "{field_name}" or r._field == "value2")'
            ),
        },
    },
    "group_by_tag": {
        "type": "stackedbars",
        "title": "Group by tag",
        "description": "Query is groupped by tag along with time",
        "unit": "n.",
        "order": 999,
        "query": {
            "influxdb": (
                "SELECT CUMULATIVE_SUM(SUM({field_name})) FROM {key} WHERE time >= '{time}'"
                " GROUP BY time(1d), metric_num"
            ),
            "influxdb2": (
                'from(bucket: "{bucket}") |> range(start: {time_start}) '
                '|> filter(fn: (r) => r._measurement == "{key}")'
                ' |> filter(fn: (r) => r._field == "{field_name}")'
                ' |> group(columns: ["metric_num"])'
                " |> aggregateWindow(every: {window}, fn: sum, createEmpty: false)"
                " |> cumulativeSum()"
            ),
        },
        "summary_query": {
            "influxdb": (
                "SELECT SUM({field_name}) FROM {key} WHERE time >= '{time}'"
                " GROUP BY time(30d), metric_num"
            ),
            "influxdb2": (
                'from(bucket: "{bucket}") |> range(start: {time_start}) '
                '|> filter(fn: (r) => r._measurement == "{key}")'
                ' |> filter(fn: (r) => r._field == "{field_name}")'
                ' |> group(columns: ["metric_num"])'
                " |> sum()"
            ),
        },
    },
    "mean_test": {
        "type": "line",
        "title": "Mean test",
        "description": "For testing purposes",
        "unit": "n.",
        "order": 999,
        "query": {
            "influxdb": (
                "SELECT MEAN({field_name}) AS {field_name} FROM {key} WHERE time >= '{time}' AND "
                "content_type = '{content_type}' AND object_id = '{object_id}'"
            ),
            "influxdb2": (
                'from(bucket: "{bucket}") |> range(start: {time_start}) '
                '|> filter(fn: (r) => r._measurement == "{key}")'
                "{content_type_filter}{object_id_filter}{field_filter}"
                " |> mean()"
                ' |> duplicate(column: "_stop", as: "_time")'
            ),
        },
    },
    "sum_test": {
        "type": "line",
        "title": "Sum test",
        "description": "For testing purposes",
        "unit": "n.",
        "order": 999,
        "query": {
            "influxdb": (
                "SELECT SUM({field_name}) AS {field_name} FROM {key} WHERE time >= '{time}' AND "
                "content_type = '{content_type}' AND object_id = '{object_id}'"
            ),
            "influxdb2": (
                'from(bucket: "{bucket}") |> range(start: {time_start}) '
                '|> filter(fn: (r) => r._measurement == "{key}")'
                "{content_type_filter}{object_id_filter}{field_filter}"
                " |> sum()"
                ' |> duplicate(column: "_stop", as: "_time")'
            ),
        },
    },
    "top_fields_mean": {
        "type": "histogram",
        "title": "Top fields mean test",
        "description": "For testing purposes",
        "top_fields": 2,
        "order": 999,
        "query": {
            "influxdb": (
                "SELECT {fields|MEAN} FROM {key} "
                "WHERE time >= '{time}' AND content_type = "
                "'{content_type}' AND object_id = '{object_id}'"
            ),
            "influxdb2": (
                'from(bucket: "{bucket}") |> range(start: {time_start}) '
                '|> filter(fn: (r) => r._measurement == "{key}")'
                "{content_type_filter}{object_id_filter}{field_filter}"
                " |> mean()"
            ),
        },
    },
}


class TestMonitoringMixin(TestOrganizationMixin):
    ORIGINAL_DB = TIMESERIES_DB["NAME"]
    TEST_DB = f"{ORIGINAL_DB}_test"

    @classmethod
    def _unregister_test_metrics(cls):
        for key in metrics.keys():
            if key in DEFAULT_METRICS:
                unregister_metric(key)

    @classmethod
    def _unregister_test_charts(cls):
        for key in charts.keys():
            if key in DEFAULT_CHARTS:
                unregister_chart(key)

    @classmethod
    def _reset_timeseries_client_state(cls):
        # The global timeseries client caches backend handles lazily, so test
        # classes must reset those cached objects whenever the test database
        # lifecycle changes.
        timeseries_db.reset(db_name=cls.TEST_DB)

    @classmethod
    def _recreate_timeseries_storage(cls):
        cls._reset_timeseries_client_state()
        timeseries_db.drop_database()
        # Reset again after dropping to avoid reusing stale cached client
        # state when create_database() opens the next connection.
        cls._reset_timeseries_client_state()
        timeseries_db.create_database()
        manage_short_retention_policy()

    @classmethod
    def setUpClass(cls):
        # By default timeseries_db.db shall connect to the database
        # defined in settings when apps are loaded. We don't want that while testing
        cls._recreate_timeseries_storage()
        cls._unregister_test_metrics()
        cls._unregister_test_charts()
        for key, value in metrics.items():
            register_metric(key, value)
        for key, value in charts.items():
            register_chart(key, value)
        cache.clear()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        cls._reset_timeseries_client_state()
        timeseries_db.drop_database()
        cls._reset_timeseries_client_state()
        cls._unregister_test_metrics()
        cls._unregister_test_charts()
        cache.clear()
        super().tearDownClass()

    def tearDown(self):
        cache.clear()
        timeseries_db.delete_metric_data()
        super().tearDown()

    def _create_general_metric(self, **kwargs):
        opts = {
            "name": "test_metric",
            "is_healthy": True,  # backward compatibility with old tests
            "is_healthy_tolerant": True,  # backward compatibility with old tests
            "configuration": "test_metric",
        }
        opts.update(kwargs)
        m = Metric(**opts)
        m.full_clean()
        m.save()
        return m

    def _create_object_metric(self, **kwargs):
        opts = kwargs.copy()
        if "content_object" not in opts:
            opts["content_object"] = self._create_user()
        if "is_healthy" not in kwargs:
            kwargs["is_healthy"] = True  # backward compatibility with old tests
        return self._create_general_metric(**opts)

    def _create_alert_settings(self, **kwargs):
        alert_s = AlertSettings(**kwargs)
        alert_s.full_clean()
        alert_s.save()
        return alert_s

    def _create_chart(self, metric=None, test_data=True, configuration="dummy"):
        m = metric or self._create_object_metric()
        if test_data:
            m.write(3, time=now() - timedelta(days=2))
            m.write(6, time=now() - timedelta(days=1))
            m.write(9, time=now())
        c = Chart(metric=m, configuration=configuration)
        c.full_clean()
        c.save()
        return c

    # UDP writes are flushed by InfluxDB in the background, so a point may not
    # be readable immediately after being written. Polling is safer than a fixed
    # sleep under CI load.
    _udp_read_max_retries = 15
    _udp_read_retry_delay = 0.2

    @property
    def _is_timeseries_udp_writes(self):
        return TIMESERIES_DB.get("OPTIONS", {}).get("udp_writes", False)

    @staticmethod
    def _is_timeseries_read_empty(result):
        # chart reads return a dict ("traces"/"x"), metric reads return a list
        if isinstance(result, dict):
            return not result.get("traces") and not result.get("x")
        return not result

    def _read_chart_or_metric(self, obj, *args, **kwargs):
        # Some callers expect an empty result, for example after deleting a
        # metric. In those cases, return immediately instead of polling.
        allow_empty = kwargs.pop("allow_empty", False)
        if not self._is_timeseries_udp_writes:
            return obj.read(*args, **kwargs)
        result = obj.read(*args, **kwargs)
        if allow_empty:
            return result
        # A UDP batch can become visible in pieces. Wait until two consecutive
        # non-empty reads match, so partial results and trailing null values do
        # not make the test proceed too early.
        retries = 0
        while retries < self._udp_read_max_retries:
            time.sleep(self._udp_read_retry_delay)
            new_result = obj.read(*args, **kwargs)
            if not self._is_timeseries_read_empty(new_result) and new_result == result:
                return new_result
            result = new_result
            retries += 1
        return result

    def _read_metric(self, metric, *args, **kwargs):
        return self._read_chart_or_metric(metric, *args, **kwargs)

    def _read_chart(self, chart, *args, **kwargs):
        return self._read_chart_or_metric(chart, *args, **kwargs)

    def _write_metric(self, metric, *args, **kwargs):
        metric.write(*args, **kwargs)
        if self._is_timeseries_udp_writes:
            # Wait for InfluxDB to expose the point instead of relying on a
            # fixed sleep, which is unreliable under load.
            self._read_chart_or_metric(metric)
