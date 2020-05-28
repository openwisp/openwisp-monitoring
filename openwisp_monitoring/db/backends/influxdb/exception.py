from influxdb.exceptions import InfluxDBClientError


class DatabaseException(object):
    client_error = InfluxDBClientError
