from .backends import TimeseriesDB, TimeseriesDBQueries  # noqa

chart_query = TimeseriesDBQueries.chart_query
default_chart_query = TimeseriesDBQueries.default_chart_query
device_data_query = TimeseriesDBQueries.device_data_query
test_query = TimeseriesDBQueries.test_query
