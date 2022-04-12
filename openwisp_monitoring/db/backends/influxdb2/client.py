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
from influxdb_client.client.exceptions import InfluxDBError
from influxdb_client.client.write_api import SYNCHRONOUS

from openwisp_monitoring.utils import retry

from ...exceptions import TimeseriesWriteException
from .. import TIMESERIES_DB

logger = logging.getLogger(__name__)

class DatabaseClient(object):
    backend_name = 'influxdb2'

    def __init__(self, db_name=None):
        self._db = None
        self.db_name = db_name or TIMESERIES_DB['NAME']
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
        "creates a new bucket if not already found"
        bucket = self.db.buckets_api().find_bucket_by_name(self.db_name)
        if bucket is None:
            bucket = self.db.buckets_api().create_bucket(bucket_name=self.db_name, org=TIMESERIES_DB["ORG"])
            logger.debug(f'Created InfluxDB2 bucket "{self.db_name}"')
        else:
            logger.debug(f'Bucket named "{self.db_name}" found')

    @retry
    def drop_database(self):
        "deletes a bucket if it exists"
        bucket = self.db.buckets_api().find_bucket_by_name(self.db_name)
        if bucket is None:
            logger.debug(f'No such bucket: "{self.db_name}"')
        else:
            self.db.buckets_api().delete_bucket(bucket)
            logger.debug(f'Bucket named "{self.db_name}" deleted')

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
