import logging

from django.utils.functional import cached_property
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.exceptions import InfluxDBError
from influxdb_client.client.write_api import SYNCHRONOUS

from openwisp_monitoring.utils import retry

from ...exceptions import TimeseriesWriteException
from .. import TIMESERIES_DB
from ..base import BaseDatabaseClient

logger = logging.getLogger(__name__)


class DatabaseClient(BaseDatabaseClient):
    backend_name = 'influxdb2'

    def __init__(self, db_name=None):
        super().__init__(db_name)
        self.client_error = InfluxDBError

    @cached_property
    def db(self):
        return InfluxDBClient(
            url=f"http://{TIMESERIES_DB['HOST']}:{TIMESERIES_DB['PORT']}",
            token=TIMESERIES_DB['TOKEN'],
            org=TIMESERIES_DB['ORG'],
            bucket=self.db_name,
        )

    @retry
    def create_database(self):
        self.write_api = self.db.write_api(write_options=SYNCHRONOUS)
        self.query_api = self.db.query_api()
        logger.debug('Initialized APIs for InfluxDB 2.0')

    @retry
    def drop_database(self):
        pass  # Implement as needed for InfluxDB 2.0

    @retry
    def query(self, query):
        return self.query_api.query(query)

    def write(self, name, values, **kwargs):
        point = Point(name).time(self._get_timestamp(kwargs.get('timestamp')))
        tags = kwargs.get('tags', {})
        for tag, value in tags.items():
            point.tag(tag, value)
        for field, value in values.items():
            point.field(field, value)
        try:
            self.write_api.write(bucket=self.db_name, record=point)
        except InfluxDBError as e:
            raise TimeseriesWriteException(str(e))

    @retry
    def get_list_retention_policies(self, name=None):
        bucket = self.db.buckets_api().find_bucket_by_name(name)
        if bucket:
            return bucket.retention_rules
        return []

    @retry
    def create_or_alter_retention_policy(self, name, duration):
        bucket = self.db.buckets_api().find_bucket_by_name(name)
        retention_rules = [{"type": "expire", "everySeconds": duration}]
        if bucket:
            bucket.retention_rules = retention_rules
            self.db.buckets_api().update_bucket(bucket=bucket)
        else:
            self.db.buckets_api().create_bucket(
                bucket_name=name,
                retention_rules=retention_rules,
                org=TIMESERIES_DB["ORG"],
            )
