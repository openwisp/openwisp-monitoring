from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from freezegun import freeze_time
from swapper import load_model

from openwisp_utils.tests import catch_signal

from .. import settings as app_settings
from ..exceptions import InvalidChartConfigException, InvalidMetricConfigException
from ..signals import post_metric_write, pre_metric_write, threshold_crossed
from ..tasks import delete_wifi_clients_and_session
from . import TestMonitoringMixin, TestWifiClientSessionMixin

start_time = timezone.now()
ten_minutes_ago = start_time - timedelta(minutes=10)
Metric = load_model('monitoring', 'Metric')
AlertSettings = load_model('monitoring', 'AlertSettings')
WifiClient = load_model('monitoring', 'WifiClient')
WifiSession = load_model('monitoring', 'WifiSession')
DeviceData = load_model('device_monitoring', 'DeviceData')
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

    def test_invalid_chart_config(self):
        c = self._create_chart(test_data=False)
        c.configuration = 'invalid'
        with self.assertRaises(InvalidChartConfigException):
            c.config_dict

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

    def test_tags(self):
        extra_tags = {'a': 'a', 'b': 'b1'}
        metric = self._create_object_metric(extra_tags=extra_tags)
        expected_tags = extra_tags.copy()
        expected_tags.update(
            {'object_id': metric.object_id, 'content_type': metric.content_type_key}
        )
        self.assertEqual(metric.tags, expected_tags)

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
        self.assertEqual(m.is_healthy, True)
        self.assertEqual(m.is_healthy_tolerant, True)

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
            tolerance_crossed=True,
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
            tolerance_crossed=True,
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
                time=None,
                current=False,
            )

    def test_metric_post_write_signals_emitted(self):
        om = self._create_object_metric()
        with catch_signal(post_metric_write) as handler:
            om.write(3, current=True, time=start_time)
            handler.assert_called_once_with(
                sender=Metric,
                metric=om,
                values={om.field_name: 3},
                signal=post_metric_write,
                time=start_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
                current=True,
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
            self.assertEqual(m.is_healthy, True)
            self.assertEqual(m.is_healthy_tolerant, True)
            self.assertEqual(Notification.objects.count(), 0)
            m.write(99, time=timezone.now() - timedelta(minutes=4))
            self.assertEqual(m.is_healthy, True)
            self.assertEqual(m.is_healthy_tolerant, True)
            self.assertEqual(Notification.objects.count(), 0)
        with self.subTest('tolerance trepassed, alerts expected'):
            m.write(99, time=timezone.now() - timedelta(minutes=6))
            m.refresh_from_db()
            self.assertEqual(m.is_healthy, False)
            self.assertEqual(m.is_healthy_tolerant, False)
            self.assertEqual(Notification.objects.count(), 1)
        with self.subTest('value back to normal, tolerance not considered'):
            m.write(71, time=timezone.now() - timedelta(minutes=7))
            m.refresh_from_db()
            self.assertEqual(m.is_healthy, True)
            self.assertEqual(m.is_healthy_tolerant, True)
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


class TestWifiClientSession(TestWifiClientSessionMixin, TestCase):
    wifi_client_model = WifiClient
    wifi_session_model = WifiSession
    device_data_model = DeviceData

    def test_wifi_client_session_created(self):
        device_data = self._save_device_data()
        self.assertEqual(WifiClient.objects.count(), 3)
        self.assertEqual(WifiSession.objects.count(), 3)
        wifi_client1 = WifiClient.objects.get(mac_address='00:ee:ad:34:f5:3b')
        self.assertEqual(wifi_client1.vendor, None)
        self.assertEqual(wifi_client1.ht, True)
        self.assertEqual(wifi_client1.vht, False)
        self.assertEqual(wifi_client1.wmm, True)
        self.assertEqual(wifi_client1.wds, False)
        self.assertEqual(wifi_client1.wps, False)

        wifi_client2 = WifiClient.objects.get(mac_address='b0:e1:7e:30:16:44')
        self.assertEqual(wifi_client2.vendor, None)
        self.assertEqual(wifi_client2.ht, True)
        self.assertEqual(wifi_client2.vht, False)
        self.assertEqual(wifi_client2.wmm, True)
        self.assertEqual(wifi_client2.wds, False)
        self.assertEqual(wifi_client2.wps, False)

        wifi_client3 = WifiClient.objects.get(mac_address='c0:ee:fb:34:f5:4b')
        self.assertEqual(wifi_client3.vendor, None)
        self.assertEqual(wifi_client3.ht, True)
        self.assertEqual(wifi_client3.vht, False)
        self.assertEqual(wifi_client3.wmm, True)
        self.assertEqual(wifi_client3.wds, False)
        self.assertEqual(wifi_client3.wps, False)

        wifi_client1_session = WifiSession.objects.get(wifi_client=wifi_client1)
        self.assertEqual(wifi_client1_session.device, device_data)
        self.assertEqual(wifi_client1_session.ssid, 'testnet')
        self.assertEqual(wifi_client1_session.interface_name, 'wlan0')
        self.assertNotEqual(wifi_client1_session.start_time, None)
        self.assertEqual(wifi_client1_session.stop_time, None)

        wifi_client2_session = WifiSession.objects.get(wifi_client=wifi_client2)
        self.assertEqual(wifi_client2_session.device, device_data)
        self.assertEqual(wifi_client2_session.ssid, 'testnet')
        self.assertEqual(wifi_client2_session.interface_name, 'wlan1')
        self.assertNotEqual(wifi_client2_session.start_time, None)
        self.assertEqual(wifi_client2_session.stop_time, None)

        wifi_client3_session = WifiSession.objects.get(wifi_client=wifi_client3)
        self.assertEqual(wifi_client3_session.device, device_data)
        self.assertEqual(wifi_client3_session.ssid, 'testnet')
        self.assertEqual(wifi_client3_session.interface_name, 'wlan1')
        self.assertNotEqual(wifi_client3_session.start_time, None)
        self.assertEqual(wifi_client3_session.stop_time, None)

    def test_opening_closing_existing_sessions(self):
        data = deepcopy(self._sample_data)
        device_data = self._create_device_data()
        self._save_device_data(device_data, data)
        self.assertEqual(WifiSession.objects.filter(stop_time=None).count(), 3)
        self.assertEqual(WifiSession.objects.count(), 3)
        self.assertEqual(WifiClient.objects.count(), 3)

        with self.subTest('Test closing session'):
            self._save_device_data(
                device_data, data={'type': 'DeviceMonitoring', 'interfaces': []}
            )
            self.assertEqual(WifiSession.objects.filter(stop_time=None).count(), 0)
            self.assertEqual(WifiSession.objects.count(), 3)
            self.assertEqual(WifiClient.objects.count(), 3)

        with self.subTest('Test re-opening session for exising clients'):
            self._save_device_data(device_data, data)
            self.assertEqual(WifiSession.objects.filter(stop_time=None).count(), 3)
            self.assertEqual(WifiSession.objects.count(), 6)
            self.assertEqual(WifiClient.objects.count(), 3)

    def test_delete_old_wifi_sessions(self):
        with freeze_time(timezone.now() - timedelta(days=6 * 31)):
            self._create_wifi_session()
        self.assertEqual(WifiSession.objects.count(), 1)
        delete_wifi_clients_and_session.delay()
        self.assertEqual(WifiSession.objects.count(), 0)

    def test_database_queries(self):
        data = deepcopy(self._sample_data)
        device_data = self._create_device_data()
        with self.subTest('Test creating new clients and sessions'):
            with self.assertNumQueries(17):
                self._save_device_data(device_data, data)

        with self.subTest('Test updating existing clients and sessions'):
            with self.assertNumQueries(5):
                self._save_device_data(device_data, data)

        with self.subTest('Test closing existing sessions'):
            with self.assertNumQueries(1):
                self._save_device_data(
                    device_data, data={'type': 'DeviceMonitoring', 'interface': []}
                )

        with self.subTest('Test new sessions for existing clients'):
            with self.assertNumQueries(5):
                self._save_device_data(device_data, data)

    @patch.object(app_settings, 'WIFI_SESSIONS_ENABLED', False)
    def test_disabling_wifi_sessions(self):
        device_data = self._create_device_data()
        with self.assertNumQueries(0):
            self._save_device_data(device_data)
        self.assertEqual(WifiClient.objects.count(), 0)
        self.assertEqual(WifiSession.objects.count(), 0)
