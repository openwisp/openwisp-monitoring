from .backends import TimeseriesDB, TimeseriesDBQueries

chart_query = TimeseriesDBQueries.chart_query
default_chart_query = TimeseriesDBQueries.default_chart_query
device_data_query = TimeseriesDBQueries.device_data_query

__all__ = ['TimeseriesDB', 'TimeseriesDBQueries']
