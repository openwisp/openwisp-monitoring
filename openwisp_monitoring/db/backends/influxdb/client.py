from openwisp_monitoring.db.backends.influx_base import BaseInfluxDatabaseClient


class DatabaseClient(BaseInfluxDatabaseClient):
    """
    Thin wrapper around the shared InfluxQL base client.

    Kept for backward compatibility with the existing backend loader and imports.
    """

    pass
