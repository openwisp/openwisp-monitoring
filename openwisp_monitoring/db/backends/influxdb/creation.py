import logging

from .. import TIMESERIES_DB

logger = logging.getLogger(__name__)


class DatabaseCreation(object):
    ORIGINAL_DB = TIMESERIES_DB['NAME']
    TEST_DB = f'{ORIGINAL_DB}_test'

    def create_database(self, database=TIMESERIES_DB['NAME']):
        """ creates database if necessary """
        db = self.get_db()
        response = db.query('SHOW DATABASES')
        items = list(response.get_points('databases'))
        databases = [database['name'] for database in items]
        # if database does not exists, create it
        if database not in databases:
            db.create_database(database)
            logger.info(f'Created influxdb database {database}')

    def drop_database(self, database=TIMESERIES_DB['NAME']):
        """ drops database if it exists """
        db = self.get_db()
        response = db.query('SHOW DATABASES')
        items = list(response.get_points('databases'))
        databases = [database['name'] for database in items]
        if database in databases:
            db.drop_database(database)
            logger.info(f'Dropped influxdb database {database}')

    def create_test_database(self):
        TIMESERIES_DB['NAME'] = self.TEST_DB
        self.create_database(self.TEST_DB)

    def drop_test_database(self):
        self.drop_database(self.TEST_DB)
        TIMESERIES_DB['NAME'] = self.ORIGINAL_DB
        self.get_db().query('DROP SERIES FROM /.*/')
