from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils.timezone import now
from swapper import load_model

from openwisp_users.tests.utils import TestOrganizationMixin

from .. import settings as app_settings
from ..utils import create_database, get_db, query

User = get_user_model()
start_time = now()
ten_minutes_ago = start_time - timedelta(minutes=10)
Chart = load_model('monitoring', 'Chart')
Metric = load_model('monitoring', 'Metric')
AlertSettings = load_model('monitoring', 'AlertSettings')


class TestMonitoringMixin(TestOrganizationMixin):
    ORIGINAL_DB = app_settings.INFLUXDB_DATABASE
    TEST_DB = '{0}_test'.format(ORIGINAL_DB)

    @classmethod
    def setUpClass(cls):
        setattr(app_settings, 'INFLUXDB_DATABASE', cls.TEST_DB)
        create_database()

    @classmethod
    def tearDownClass(cls):
        get_db().drop_database(cls.TEST_DB)
        setattr(app_settings, 'INFLUXDB_DATABASE', cls.ORIGINAL_DB)

    def tearDown(self):
        query('DROP SERIES FROM /.*/')

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
