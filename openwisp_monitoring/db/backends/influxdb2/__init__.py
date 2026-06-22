from ..base import BackendQueryBundle
from .client import DatabaseClient
from .queries import chart_query, default_chart_query, device_data_query

queries = BackendQueryBundle(
    chart_query=chart_query,
    default_chart_query=default_chart_query,
    device_data_query=device_data_query,
)

__all__ = ["DatabaseClient", "queries"]
