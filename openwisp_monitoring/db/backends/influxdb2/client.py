import logging
import operator
import re
from collections import OrderedDict
from datetime import datetime

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.exceptions import InfluxDBError, BucketRetentionRules
from influxdb_client.client.write_api import SYNCHRONOUS

from openwisp_monitoring.utils import retry

from ...exceptions import TimeseriesWriteException
from .. import TIMESERIES_DB

logger = logging.getLogger(__name__)

class DatabaseClient(object):
    backend_name = 'influxdb2'

    def __init__(self, db_name=None):
        self._db = None
        self.client_error = InfluxDBError
        self.write_api = None
        self.query_api = None

    @cached_property
    def db(self):
        "Returns an InfluxDBClient instance"
        return InfluxDBClient{
            url = f"http://{TIMESERIES_DB["HOST"]}:{TIMESERIES_DB["PORT"]}",
            bucket = self.db_name,
            token = TIMESERIES_DB["TOKEN"]
        }

    @retry
    def create_database(self):
        "initialize APIs required for writing and querying data from influxdb database"
        logger.debug(f'quert_api and write_api for {str(self.db)} initiated')
        self.write_api = self.db.write_api(write_options=SYNCHRONOUS)
        self.query_api = self.db.query_api()

    @retry
    def drop_database(self):
        "deletes all buckets"
        pass

    @retry
    def query(self, query):
        resultObject = self.query_api.query(query)
        return resultObject

    def standardizeResult(self, resultObject):
        """
            return the query result in the form of a list of dictionaries
            to make all the back ends uniform
        """
        result = list()

        for table in tables:
            for row in table.records:
                listObject = {
                    "time": row["_time"],
                    "field": row["_field"],
                    "value": row["_value"],
                    "mesurement": row["_measurement"]
                }
                result.append(listObject)

        return result

    def write(self, name, values, **kwargs):
        """
            values can either be a list or a string
        """
        timestamp = kwargs.get('timestamp') or now()
        point = Point(name).time(timestamp.isoformat(sep='T', timespec='microseconds'))
        tags = kwargs.get('tags')
        values = kwargs.get('values')

        for tag in tags:
            if type(tag) == str:
                tag = tag.split('=')
            point.tag(tag[0], tag[1])

        for value in values:
            if type(value) == str:
                value = tag.split('=')
            point.field(value[0], value[1])

        try:
            self.write_api.write(bucket=self.db_name, record=point)
        except Exception as e:
            except Exception as exception:
                logger.warning(f'got exception while writing to tsdb: {exception}')
                if isinstance(exception, self.client_error):
                    exception_code = getattr(exception, 'code', None)
                    exception_message = getattr(exception, 'content')
                    if (
                        exception_code == 400
                        and 'points beyond retention policy dropped' in exception_message
                    ):
                        return
                raise TimeseriesWriteException

    @retry
    def get_list_retention_policies(self, name=None):
        if name is None:
            logger.warning(f'no bucket name provided')
            return None
        bucket = self.db.buckets_api().find_bucket_by_name(name)
        if bucket is None:
            logger.warning(f'Bucket with name - {name} not found')
            return None
        return bucket.retention_rules

    @retry
    def create_or_alter_retention_policy(self, name, duration):
        """alters the retention policy if bucket with the given name exists,
        otherwise create a new bucket"""
        bucket = self.db.buckets_api().find_bucket_by_name(name)
        retention_rules = BucketRetentionRules(type="expire", every_seconds=duration)
        if not bucket is None:
            bucket.retention_rules = retention_rules
            self.db.buckets_api().update_bucket(bucket=bucket)
            logger.warning(f'Retention policies for bucket '{name}' have been updated')
        else:
            bucket = buckets_api.create_bucket(bucket_name=name, retention_rules=retention_rules, org=TIMESERIES_DB["ORG"])
            logger.warning(f'Bucket '{name}' with specified retention polcies has been created')
