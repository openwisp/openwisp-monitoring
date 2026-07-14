from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Self, TypedDict

from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError

TimeseriesFields = Mapping[str, Any]
TimeseriesTags = Mapping[str, Any]
TimeseriesPoint = dict[str, Any]
FieldSelection = str | Sequence[str]
ChartQueryParams = dict[str, Any]


class BatchWritePayload(TypedDict, total=False):
    name: str
    values: TimeseriesFields
    tags: TimeseriesTags
    timestamp: Any
    database: str | None
    retention_policy: str | None
    current: bool | str
    metric: Any
    check_threshold_kwargs: Mapping[str, Any]


@dataclass(frozen=True)
class BackendQueryBundle:
    chart_query: Mapping[str, Mapping[str, str]]
    default_chart_query: object
    device_data_query: object
    summary_query: Mapping[str, Mapping[str, str]] | None = None

    def validate(self, backend_name: str) -> Self:
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
        if self.summary_query is not None:
            invalid_summary_query = []
            for chart_name, chart_config in self.summary_query.items():
                if (
                    not isinstance(chart_config, Mapping)
                    or backend_name not in chart_config
                ):
                    invalid_summary_query.append(chart_name)
            if invalid_summary_query:
                joined = ", ".join(sorted(invalid_summary_query))
                raise ImproperlyConfigured(
                    "Backend query bundle is missing the "
                    f"'{backend_name}' summary key for: {joined}"
                )
        if self.default_chart_query is None:
            raise ImproperlyConfigured(
                "Backend query bundle must define default_chart_query."
            )
        if isinstance(self.default_chart_query, (list, tuple)):
            if not self.default_chart_query:
                raise ImproperlyConfigured(
                    "Backend query bundle must define a non-empty default_chart_query."
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
    queries: BackendQueryBundle | None = None

    @classmethod
    def validate_settings(cls, config: Mapping[str, Any] | None) -> Mapping[str, Any]:
        if config is None or not hasattr(config, "__contains__"):
            raise DatabaseError("No TIMESERIES_DATABASE specified in settings")
        for field in cls.required_settings:
            if field not in config:
                raise ImproperlyConfigured(
                    f'"{field}" field is not declared in TIMESERIES_DATABASE'
                )
        return config

    def attach_queries(self, queries: BackendQueryBundle) -> Self:
        self.queries = queries
        return self

    def reset(self, db_name: str | None = None) -> None:
        if db_name is not None:
            self.db_name = db_name

    def get_default_chart_query(self, has_object_scope: bool = False) -> str:
        default_query = self.queries.default_chart_query
        resolver = getattr(default_query, "resolve", None)
        if callable(resolver):
            return resolver(has_object_scope=has_object_scope)
        if isinstance(default_query, str):
            return default_query
        if isinstance(default_query, (list, tuple)):
            if not default_query:
                raise ImproperlyConfigured(
                    "Backend query bundle must define a non-empty default_chart_query."
                )
            query = default_query[0]
            if has_object_scope and len(default_query) > 1:
                query = f"{query}{default_query[1]}"
            return query
        raise ImproperlyConfigured(
            "Unsupported default_chart_query descriptor for the selected backend."
        )

    @abstractmethod
    def create_database(self) -> None:
        pass

    @abstractmethod
    def drop_database(self) -> None:
        pass

    @property
    @abstractmethod
    def use_udp(self) -> bool:
        pass

    @abstractmethod
    def create_or_alter_retention_policy(self, name: str, duration: str) -> None:
        pass

    @abstractmethod
    def query(self, query: str, precision: str | None = None, **kwargs: Any) -> Any:
        pass

    @abstractmethod
    def write(self, name: str, values: TimeseriesFields, **kwargs: Any) -> None:
        pass

    @abstractmethod
    def batch_write(self, metric_data: Sequence[BatchWritePayload]) -> None:
        pass

    @abstractmethod
    def read(
        self,
        key: str,
        fields: FieldSelection,
        tags: TimeseriesTags | None,
        **kwargs: Any,
    ) -> list[TimeseriesPoint]:
        pass

    @abstractmethod
    def get_list_query(self, query: str, precision: str = "s") -> list[TimeseriesPoint]:
        pass

    @abstractmethod
    def get_list_retention_policies(self) -> list[TimeseriesPoint]:
        pass

    @abstractmethod
    def delete_metric_data(
        self, key: str | None = None, tags: TimeseriesTags | None = None
    ) -> None:
        pass

    @abstractmethod
    def delete_series(
        self, key: str | None = None, tags: TimeseriesTags | None = None
    ) -> None:
        pass

    @abstractmethod
    def validate_query(self, query: str) -> bool:
        pass

    @abstractmethod
    def get_query(
        self,
        chart_type: str,
        params: ChartQueryParams,
        time: Any,
        group_map: Mapping[Any, str],
        summary: bool = False,
        fields: Sequence[str] | None = None,
        query: str | None = None,
        timezone: str | None = None,
    ) -> str:
        pass

    @abstractmethod
    def _get_top_fields(
        self,
        query: str | None,
        params: ChartQueryParams,
        chart_type: str,
        group_map: Mapping[Any, str],
        number: int,
        time: Any,
        timezone: str | None = None,
    ) -> list[str]:
        pass
