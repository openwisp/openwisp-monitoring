from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from swapper import load_model

from openwisp_utils.tests import catch_signal

from ..signals import alert_settings_crossed, post_metric_write, pre_metric_write
from ..utils import query, write
from . import TestMonitoringMixin

start_time = timezone.now()
ten_minutes_ago = start_time - timedelta(minutes=10)
Metric = load_model('monitoring', 'Metric')


class TestModels(TestMonitoringMixin, TestCase):
    def test_general_metric_str(self):
        m = Metric(name='Test metric')
        self.assertEqual(str(m), m.name)

    def test_chart_str(self):
        c = self._create_chart()
        self.assertEqual(str(c), c.label)

    def test_chart_no_valid_config(self):
        c = self._create_chart()
        c.configuration = 'invalid'
        try:
            c.full_clean()
        except ValidationError as e:
            self.assertIn('configuration', e.message_dict)
        else:
            self.fail()

    def test_general_codename(self):
        m = Metric(name='Test metric-(1)')
        self.assertEqual(m.codename, 'test_metric_1')
        m = Metric()
        self.assertEqual(m.codename, '')

    def test_metric_key_contains_dash(self):
        m = self._create_general_metric(key='br-lan')
        self.assertEqual(m.key, 'br_lan')

    def test_metric_key_contains_dot(self):
        m = self._create_general_metric(key='eth0.2')
        self.assertEqual(m.key, 'eth0_2')

    def test_object_metric_str(self):
        obj = self._create_user()
        om = self._create_object_metric(name='Logins', content_object=obj)
        om.refresh_from_db()
        expected = '{0} (User: {1})'.format(om.name, obj)
        self.assertEqual(str(om), expected)

    def test_general_key(self):
        m = self._create_general_metric()
        self.assertEqual(m.key, m.codename)

    def test_object_key(self):
        om = self._create_object_metric()
        self.assertEqual(om.key, om.codename)

    def test_custom_get_or_create(self):
        m, created = Metric._get_or_create(name='lan', key='br-lan')
        self.assertTrue(created)
        m2, created = Metric._get_or_create(name='lan', key='br-lan')
        self.assertEqual(m.id, m2.id)
        self.assertFalse(created)

    def test_write(self):
        write('test_write', dict(value=2), database=self.TEST_DB)
        measurement = list(query('select * from test_write').get_points())[0]
        self.assertEqual(measurement['value'], 2)

    def test_general_write(self):
        m = self._create_general_metric(name='Sync test')
        m.write(1)
        measurement = list(query('select * from sync_test').get_points())[0]
        self.assertEqual(measurement['value'], 1)

    def test_object_write(self):
        om = self._create_object_metric()
        om.write(3)
        content_type = '.'.join(om.content_type.natural_key())
        q = (
            "select * from test_metric WHERE object_id = '{0}'"
            " AND content_type = '{1}'".format(om.object_id, content_type)
        )
        measurement = list(query(q).get_points())[0]
        self.assertEqual(measurement['value'], 3)

    def test_general_same_key_different_fields(self):
        down = self._create_general_metric(
            name='traffic (download)', key='traffic', field_name='download'
        )
        down.write(200)
        up = self._create_general_metric(
            name='traffic (upload)', key='traffic', field_name='upload'
        )
        up.write(100)
        measurement = list(query('select download from traffic').get_points())[0]
        self.assertEqual(measurement['download'], 200)
        measurement = list(query('select upload from traffic').get_points())[0]
        self.assertEqual(measurement['upload'], 100)

    def test_object_same_key_different_fields(self):
        user = self._create_user()
        user_down = self._create_object_metric(
            name='traffic (download)',
            key='traffic',
            field_name='download',
            content_object=user,
        )
        user_down.write(200)
        user_up = self._create_object_metric(
            name='traffic (upload)',
            key='traffic',
            field_name='upload',
            content_object=user,
        )
        user_up.write(100)
        content_type = '.'.join(user_down.content_type.natural_key())
        q = (
            "select download from traffic WHERE object_id = '{0}'"
            " AND content_type = '{1}'".format(user_down.object_id, content_type)
        )
        measurement = list(query(q).get_points())[0]
        self.assertEqual(measurement['download'], 200)
        q = (
            "select upload from traffic WHERE object_id = '{0}'"
            " AND content_type = '{1}'".format(user_up.object_id, content_type)
        )
        measurement = list(query(q).get_points())[0]
        self.assertEqual(measurement['upload'], 100)

    def test_read_general_metric(self):
        m = self._create_general_metric(name='load')
        m.write(50, check=False)
        self.assertEqual(m.read()[0][m.field_name], 50)
        m.write(1, check=False)
        self.assertEqual(m.read()[0][m.field_name], 50)
        self.assertEqual(m.read(order='time DESC')[0][m.field_name], 1)

    def test_read_object_metric(self):
        om = self._create_object_metric(name='load')
        om.write(50)
        om.write(3)
        om.read(extra_fields='*')
        self.assertEqual(om.read()[0][om.field_name], 50)

    def test_alert_settings_max_seconds(self):
        m = self._create_general_metric(name='load')
        try:
            self._create_alert_settings(
                metric=m, operator='>', value=90, seconds=9999999
            )
        except ValidationError as e:
            self.assertIn('seconds', e.message_dict)
        else:
            self.fail('ValidationError not raised')

    def test_alert_settings_is_crossed_error(self):
        m = self._create_general_metric(name='load')
        alert_s = self._create_alert_settings(
            metric=m, operator='>', value=90, seconds=0
        )
        with self.assertRaises(ValueError):
            alert_s._is_crossed_by(alert_s, start_time)

    def test_alert_settings_is_crossed_immediate(self):
        m = self._create_general_metric(name='load')
        alert_s = self._create_alert_settings(
            metric=m, operator='>', value=90, seconds=0
        )
        self.assertFalse(alert_s._is_crossed_by(80, start_time))
        self.assertTrue(alert_s._is_crossed_by(91, start_time))
        self.assertTrue(alert_s._is_crossed_by(100, start_time))
        self.assertTrue(alert_s._is_crossed_by(100))
        self.assertFalse(alert_s._is_crossed_by(90, start_time))
        alert_s.operator = '<'
        alert_s.save()
        self.assertTrue(alert_s._is_crossed_by(80))

    def test_alert_settings_is_crossed_deferred(self):
        m = self._create_general_metric(name='load')
        alert_s = self._create_alert_settings(
            metric=m, operator='>', value=90, seconds=60 * 9
        )
        self.assertFalse(alert_s._is_crossed_by(95, start_time))
        self.assertTrue(alert_s._is_crossed_by(95, ten_minutes_ago))
        self.assertFalse(alert_s._is_crossed_by(80, start_time))
        self.assertFalse(alert_s._is_crossed_by(80, ten_minutes_ago))

    def test_alert_settings_is_crossed_deferred_2(self):
        self._create_admin()
        m = self._create_general_metric(name='load')
        self._create_alert_settings(metric=m, operator='>', value=90, seconds=60)
        m.write(60)
        m.write(99)
        self.assertTrue(m.is_healthy)

    def test_general_check_alert_settings_no_exception(self):
        m = self._create_general_metric()
        m.check_alert_settings(1)

    def test_general_metric_signal_emitted(self):
        m = self._create_general_metric(name='load')
        alert_s = self._create_alert_settings(
            metric=m, operator='>', value=90, seconds=0
        )
        with catch_signal(alert_settings_crossed) as handler:
            m.check_alert_settings(91)
        handler.assert_called_once_with(
            alert_settings=alert_s,
            metric=m,
            target=None,
            sender=Metric,
            signal=alert_settings_crossed,
        )

    def test_object_metric_signal_emitted(self):
        om = self._create_object_metric()
        alert_s = self._create_alert_settings(
            metric=om, operator='>', value=90, seconds=0
        )
        with catch_signal(alert_settings_crossed) as handler:
            om.check_alert_settings(91)
        handler.assert_called_once_with(
            alert_settings=alert_s,
            metric=om,
            target=om.content_object,
            sender=Metric,
            signal=alert_settings_crossed,
        )

    def test_metric_pre_write_signals_emitted(self):
        om = self._create_object_metric()
        with catch_signal(pre_metric_write) as handler:
            om.write(3)
            handler.assert_called_once_with(
                sender=Metric,
                metric=om,
                values={om.field_name: 3},
                signal=pre_metric_write,
            )

    def test_metric_post_write_signals_emitted(self):
        om = self._create_object_metric()
        with catch_signal(post_metric_write) as handler:
            om.write(3)
            handler.assert_called_once_with(
                sender=Metric,
                metric=om,
                values={om.field_name: 3},
                signal=post_metric_write,
            )
