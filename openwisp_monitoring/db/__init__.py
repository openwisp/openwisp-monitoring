from .backends import timeseries_db

chart_query = timeseries_db.queries.chart_query
default_chart_query = timeseries_db.queries.default_chart_query
device_data_query = timeseries_db.queries.device_data_query

__all__ = ['timeseries_db', 'chart_query', 'default_chart_query', 'device_data_query']
