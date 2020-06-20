from datetime import timedelta

from django.utils.timezone import now
from swapper import load_model

from openwisp_users.tests.utils import TestOrganizationMixin

from ...db import timeseries_db
from ...db.backends import TIMESERIES_DB

start_time = now()
ten_minutes_ago = start_time - timedelta(minutes=10)
Chart = load_model('monitoring', 'Chart')
Metric = load_model('monitoring', 'Metric')
AlertSettings = load_model('monitoring', 'AlertSettings')


class TestMonitoringMixin(TestOrganizationMixin):
    ORIGINAL_DB = TIMESERIES_DB['NAME']
    TEST_DB = f'{ORIGINAL_DB}_test'

    @classmethod
    def setUpClass(cls):
        # By default timeseries_db.get_db shall connect to the database
        # defined in settings when apps are loaded. We don't want that while testing
        timeseries_db.db_name = cls.TEST_DB
        del timeseries_db.get_db
        timeseries_db.create_database()

    @classmethod
    def tearDownClass(cls):
        timeseries_db.drop_database()

    def tearDown(self):
        timeseries_db.delete_metric_data()

    def _create_general_metric(self, **kwargs):
        opts = {
            'name': 'test_metric',
            'is_healthy': True,  # backward compatibility with old tests
        }
        opts.update(kwargs)
        m = Metric(**opts)
        m.full_clean()
        m.save()
        return m

    def _create_object_metric(self, **kwargs):
        opts = kwargs.copy()
        if 'content_object' not in opts:
            opts['content_object'] = self._create_user()
        if 'is_healthy' not in kwargs:
            kwargs['is_healthy'] = True  # backward compatibility with old tests
        return self._create_general_metric(**opts)

    def _create_alert_settings(self, **kwargs):
        alert_s = AlertSettings(**kwargs)
        alert_s.full_clean()
        alert_s.save()
        return alert_s

    def _create_chart(
        self, metric=None, test_data=True, configuration='dummy',
    ):
        m = metric or self._create_object_metric()
        if test_data:
            m.write(3, time=now() - timedelta(days=2))
            m.write(6, time=now() - timedelta(days=1))
            m.write(9, time=now())
        c = Chart(metric=m, configuration=configuration,)
        c.full_clean()
        c.save()
        return c
