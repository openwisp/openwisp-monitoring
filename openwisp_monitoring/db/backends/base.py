from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass

from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError


@dataclass(frozen=True)
class BackendQueryBundle:
    chart_query: Mapping
    default_chart_query: object
    device_data_query: object

    def validate(self, backend_name):
        if not isinstance(self.chart_query, Mapping):
            raise ImproperlyConfigured(
                "Backend query bundle must define chart_query as a mapping."
            )
        invalid_chart_query = []
        for chart_name, chart_config in self.chart_query.items():
            if (
                not isinstance(chart_config, Mapping)
                or backend_name not in chart_config
            ):
                invalid_chart_query.append(chart_name)
        if invalid_chart_query:
            joined = ", ".join(sorted(invalid_chart_query))
            raise ImproperlyConfigured(
                f"Backend query bundle is missing the '{backend_name}' key for: {joined}"
            )
        if self.default_chart_query is None:
            raise ImproperlyConfigured(
                "Backend query bundle must define default_chart_query."
            )
        formatter = getattr(self.device_data_query, "format", None)
        if not callable(formatter):
            raise ImproperlyConfigured(
                "Backend query bundle must define device_data_query.format()."
            )
        return self


class BaseTimeseriesClient(ABC):
    backend_name = None
    client_error = Exception
    required_settings = ("BACKEND", "NAME")
    queries = None

    @classmethod
    def validate_settings(cls, config):
        if config is None or not hasattr(config, "__contains__"):
            raise DatabaseError("No TIMESERIES_DATABASE specified in settings")
        for field in cls.required_settings:
            if field not in config:
                raise ImproperlyConfigured(
                    f'"{field}" field is not declared in TIMESERIES_DATABASE'
                )
        return config

    def attach_queries(self, queries):
        self.queries = queries
        return self

    def reset(self, db_name=None):
        if db_name is not None:
            self.db_name = db_name

    def get_default_chart_query(self, has_object_scope=False):
        default_query = self.queries.default_chart_query
        resolver = getattr(default_query, "resolve", None)
        if callable(resolver):
            return resolver(has_object_scope=has_object_scope)
        if isinstance(default_query, str):
            return default_query
        if isinstance(default_query, (list, tuple)):
            query = default_query[0]
            if has_object_scope and len(default_query) > 1:
                query = f"{query}{default_query[1]}"
            return query
        raise ImproperlyConfigured(
            "Unsupported default_chart_query descriptor for the selected backend."
        )

    @abstractmethod
    def create_database(self):
        pass

    @abstractmethod
    def drop_database(self):
        pass

    @property
    @abstractmethod
    def use_udp(self):
        pass

    @abstractmethod
    def create_or_alter_retention_policy(self, name, duration):
        pass

    @abstractmethod
    def query(self, query, precision=None, **kwargs):
        pass

    @abstractmethod
    def write(self, name, values, **kwargs):
        pass

    @abstractmethod
    def batch_write(self, metric_data):
        pass

    @abstractmethod
    def read(self, key, fields, tags, **kwargs):
        pass

    @abstractmethod
    def get_list_query(self, query, precision="s"):
        pass

    @abstractmethod
    def get_list_retention_policies(self):
        pass

    @abstractmethod
    def delete_metric_data(self, key=None, tags=None):
        pass

    @abstractmethod
    def delete_series(self, key=None, tags=None):
        pass

    @abstractmethod
    def validate_query(self, query):
        pass

    @abstractmethod
    def get_query(
        self,
        chart_type,
        params,
        time,
        group_map,
        summary=False,
        fields=None,
        query=None,
        timezone=None,
    ):
        pass

    @abstractmethod
    def _get_top_fields(
        self,
        query,
        params,
        chart_type,
        group_map,
        number,
        time,
        timezone=None,
    ):
        pass
