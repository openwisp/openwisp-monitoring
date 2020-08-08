from celery import shared_task

from ..db import timeseries_db
from ..db.exceptions import TimeseriesWriteException
from .settings import RETRY_OPTIONS


@shared_task(bind=True, autoretry_for=(TimeseriesWriteException,), **RETRY_OPTIONS)
def timeseries_write(self, name, values, **kwargs):
    """
    write with exponential backoff on a failure
    """
    timeseries_db.write(name, values, **kwargs)
