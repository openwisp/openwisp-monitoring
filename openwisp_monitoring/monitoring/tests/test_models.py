from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from swapper import load_model

from openwisp_utils.tests import catch_signal

from ..exceptions import InvalidMetricConfigException
from ..signals import post_metric_write, pre_metric_write, threshold_crossed
from . import TestMonitoringMixin

start_time = timezone.now()
ten_minutes_ago = start_time - timedelta(minutes=10)
Metric = load_model('monitoring', 'Metric')
AlertSettings = load_model('monitoring', 'AlertSettings')
Notification = load_model('openwisp_notifications', 'Notification')


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

    def test_metric_no_valid_config(self):
        m = self._create_object_metric()
        m.configuration = 'invalid'
        with self.assertRaises(InvalidMetricConfigException):
            m.full_clean()

    def test_metric_related_fields(self):
        m = self._create_object_metric()
        self.assertEqual(m.related_fields, [])
        m.configuration = 'ping'
        m.full_clean()
        self.assertEqual(m.related_fields, ['loss', 'rtt_min', 'rtt_max', 'rtt_avg'])

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
        m, created = Metric._get_or_create(name='lan', configuration='test_metric')
        self.assertTrue(created)
        m2, created = Metric._get_or_create(name='lan', configuration='test_metric')
        self.assertEqual(m.id, m2.id)
        self.assertFalse(created)

    def test_get_or_create_renamed(self):
        m, created = Metric._get_or_create(name='lan', configuration='test_metric')
        self.assertTrue(created)
        m.name = 'renamed'
        m.save()
        m2, created = Metric._get_or_create(name='lan', configuration='test_metric')
        self.assertEqual(m.id, m2.id)
        self.assertEqual(m2.name, m.name)
        self.assertFalse(created)

    def test_get_or_create_renamed_object(self):
        obj = self._create_user()
        ct = ContentType.objects.get_for_model(get_user_model())
        m, created = Metric._get_or_create(
            name='logins',
            configuration='test_metric',
            content_type=ct,
            object_id=obj.pk,
        )
        self.assertTrue(created)
        m.name = 'renamed'
        m.save()
        m2, created = Metric._get_or_create(
            name='logins',
            configuration='test_metric',
            content_type=ct,
            object_id=obj.pk,
        )
        self.assertEqual(m.id, m2.id)
        self.assertEqual(m2.name, m.name)
        self.assertFalse(created)

    def test_metric_write_wrong_related_fields(self):
        m = self._create_general_metric(name='ping', configuration='ping')
        extra_values = {'reachable': 0, 'rtt_avg': 0.51, 'rtt_max': 0.6, 'rtt_min': 0.4}
        with self.assertRaisesRegex(
            ValueError, '"reachable" not defined in metric configuration'
        ):
            m.write(1, extra_values=extra_values)

    def test_read_general_metric(self):
        m = self._create_general_metric(name='load')
        m.write(50, check=False)
        self.assertEqual(m.read()[0][m.field_name], 50)
        m.write(1, check=False)
        self.assertEqual(m.read()[0][m.field_name], 50)
        self.assertEqual(m.read(order='-time')[0][m.field_name], 1)

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
                metric=m,
                custom_operator='>',
                custom_threshold=90,
                custom_tolerance=9999999,
            )
        except ValidationError as e:
            self.assertIn('custom_tolerance', e.message_dict)
        else:
            self.fail('ValidationError not raised')

    def test_threshold_is_crossed_error(self):
        m = self._create_general_metric(name='load')
        alert_s = self._create_alert_settings(
            metric=m, custom_operator='>', custom_threshold=90, custom_tolerance=0
        )
        with self.assertRaises(ValueError):
            alert_s._is_crossed_by(alert_s, start_time)

    def test_threshold_is_crossed_immediate(self):
        m = self._create_general_metric(name='load')
        alert_s = self._create_alert_settings(
            metric=m, custom_operator='>', custom_threshold=90, custom_tolerance=0
        )
        self.assertFalse(alert_s._is_crossed_by(80, start_time))
        self.assertTrue(alert_s._is_crossed_by(91, start_time))
        self.assertTrue(alert_s._is_crossed_by(100, start_time))
        self.assertTrue(alert_s._is_crossed_by(100))
        self.assertFalse(alert_s._is_crossed_by(90, start_time))
        alert_s.custom_operator = '<'
        alert_s.save()
        self.assertTrue(alert_s._is_crossed_by(80))

    def test_threshold_is_crossed_deferred(self):
        m = self._create_general_metric(name='load')
        alert_s = self._create_alert_settings(
            metric=m, custom_operator='>', custom_threshold=90, custom_tolerance=9
        )
        self.assertFalse(alert_s._is_crossed_by(95, start_time))
        self.assertTrue(alert_s._is_crossed_by(95, ten_minutes_ago))
        self.assertFalse(alert_s._is_crossed_by(80, start_time))
        self.assertFalse(alert_s._is_crossed_by(80, ten_minutes_ago))

    def test_threshold_is_crossed_deferred_2(self):
        self._create_admin()
        m = self._create_general_metric(name='load')
        self._create_alert_settings(
            metric=m, custom_operator='>', custom_threshold=90, custom_tolerance=1
        )
        m.write(60)
        m.write(99)
        self.assertTrue(m.is_healthy)

    def test_general_check_threshold_no_exception(self):
        m = self._create_general_metric()
        m.check_threshold(1)

    def test_general_metric_signal_emitted(self):
        m = self._create_general_metric(name='load')
        alert_s = self._create_alert_settings(
            metric=m, custom_operator='>', custom_threshold=90, custom_tolerance=0
        )
        with catch_signal(threshold_crossed) as handler:
            m.check_threshold(91)
        handler.assert_called_once_with(
            alert_settings=alert_s,
            first_time=False,
            metric=m,
            target=None,
            sender=Metric,
            signal=threshold_crossed,
        )

    def test_object_metric_signal_emitted(self):
        om = self._create_object_metric()
        alert_s = self._create_alert_settings(
            metric=om, custom_operator='>', custom_threshold=90, custom_tolerance=0
        )
        with catch_signal(threshold_crossed) as handler:
            om.check_threshold(91)
        handler.assert_called_once_with(
            alert_settings=alert_s,
            first_time=False,
            metric=om,
            target=om.content_object,
            sender=Metric,
            signal=threshold_crossed,
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

    def test_clean_default_threshold_values(self):
        m = self._create_general_metric(configuration='ping')
        alert_s = AlertSettings(metric=m)
        with self.subTest('Store default values'):
            alert_s.custom_operator = alert_s.operator
            alert_s.custom_threshold = alert_s.threshold
            alert_s.custom_tolerance = alert_s.tolerance
            alert_s.full_clean()
            self.assertIsNone(alert_s.custom_operator)
            self.assertIsNone(alert_s.custom_threshold)
            self.assertIsNone(alert_s.custom_tolerance)
        with self.subTest('Store default and custom values'):
            alert_s.custom_operator = alert_s.operator
            alert_s.custom_threshold = 0.5
            alert_s.custom_tolerance = 2
            alert_s.full_clean()
            self.assertIsNone(alert_s.custom_operator)
            self.assertEqual(alert_s.custom_threshold, 0.5)
            self.assertEqual(alert_s.custom_tolerance, 2)

    def test_alert_settings_tolerance_default(self):
        m = self._create_general_metric(name='load')
        alert_s = AlertSettings(metric=m)
        self.assertIsNone(alert_s.custom_tolerance)

    def test_tolerance(self):
        self._create_admin()
        m = self._create_general_metric(name='load')
        self._create_alert_settings(
            metric=m, custom_operator='>', custom_threshold=90, custom_tolerance=5
        )
        with self.subTest('within tolerance, no alerts expected'):
            m.write(99, time=timezone.now() - timedelta(minutes=2))
            self.assertTrue(m.is_healthy)
            self.assertEqual(Notification.objects.count(), 0)
            m.write(99, time=timezone.now() - timedelta(minutes=4))
            self.assertTrue(m.is_healthy)
            self.assertEqual(Notification.objects.count(), 0)
        with self.subTest('tolerance trepassed, alerts expected'):
            m.write(99, time=timezone.now() - timedelta(minutes=6))
            m.refresh_from_db()
            self.assertFalse(m.is_healthy)
            self.assertEqual(Notification.objects.count(), 1)
        with self.subTest('value back to normal, tolerance not considered'):
            m.write(71, time=timezone.now() - timedelta(minutes=7))
            m.refresh_from_db()
            self.assertTrue(m.is_healthy)
            self.assertEqual(Notification.objects.count(), 2)

    def test_time_crossed(self):
        m = self._create_general_metric(name='load')
        a = self._create_alert_settings(
            metric=m, custom_operator='>', custom_threshold=90, custom_tolerance=5
        )

        now = timezone.now()
        self.assertFalse(a._time_crossed(now))
        self.assertFalse(a._time_crossed(now - timedelta(minutes=1)))
        self.assertFalse(a._time_crossed(now - timedelta(minutes=4)))
        self.assertTrue(a._time_crossed(now - timedelta(minutes=5)))
        self.assertTrue(a._time_crossed(now - timedelta(minutes=6)))

    def test_get_time_str(self):
        m = self._create_general_metric(name='load')
        now = timezone.now()
        self.assertEqual(m._get_time(now.isoformat()), now)
