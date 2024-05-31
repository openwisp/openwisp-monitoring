import logging

from django.utils.functional import cached_property

from openwisp_monitoring.utils import retry

logger = logging.getLogger(__name__)


class BaseDatabaseClient:
    def __init__(self, db_name=None):
        self._db = None
        self.db_name = db_name

    @cached_property
    def db(self):
        raise NotImplementedError("Subclasses must implement `db` method")

    @retry
    def create_database(self):
        raise NotImplementedError("Subclasses must implement `create_database` method")

    @retry
    def drop_database(self):
        raise NotImplementedError("Subclasses must implement `drop_database` method")

    @retry
    def query(self, query):
        raise NotImplementedError("Subclasses must implement `query` method")

    def write(self, name, values, **kwargs):
        raise NotImplementedError("Subclasses must implement `write` method")

    def get_list_retention_policies(self, name=None):
        raise NotImplementedError(
            "Subclasses must implement `get_list_retention_policies` method"
        )

    def create_or_alter_retention_policy(self, name, duration):
        raise NotImplementedError(
            "Subclasses must implement `create_or_alter_retention_policy` method"
        )
