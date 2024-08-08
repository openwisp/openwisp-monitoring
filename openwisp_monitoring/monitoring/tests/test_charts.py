import json
from datetime import date, timedelta
from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.test import TestCase
from django.utils.timezone import now
from swapper import load_model

from openwisp_utils.tests import capture_stderr

from .. import settings as app_settings
from ..configuration import (
    CHART_CONFIGURATION_CHOICES,
    DEFAULT_DASHBOARD_TRAFFIC_CHART,
    get_chart_configuration,
    register_chart,
    unregister_chart,
)
from . import TestMonitoringMixin, charts

Chart = load_model('monitoring', 'Chart')


class TestCharts(TestMonitoringMixin, TestCase):
    """Tests for functionalities related to charts"""

    def test_read(self):
        c = self._create_chart()
        data = self._read_chart(c)
        key = c.metric.field_name
        self.assertIn('x', data)
        self.assertIn('traces', data)
        self.assertEqual(len(data['x']), 3)
        charts = data['traces']
        self.assertEqual(charts[0][0], key)
        self.assertEqual(len(charts[0][1]), 3)
        self.assertEqual(charts[0][1], [3, 6, 9])

    def test_read_summary_avg(self):
        m = self._create_object_metric(name='summary_avg')
        c = self._create_chart(metric=m, test_data=False, configuration='mean_test')
        m.write(1, time=now() - timedelta(days=2))
        m.write(2, time=now() - timedelta(days=1))
        m.write(3, time=now())
        data = self._read_chart(c)
        self.assertEqual(data['summary'], {'value': 2})

    def test_read_summary_sum(self):
        m = self._create_object_metric(name='summary_sum')
        c = self._create_chart(metric=m, test_data=False, configuration='sum_test')
        m.write(5, time=now() - timedelta(days=2))
        m.write(4, time=now() - timedelta(days=1))
        m.write(1, time=now())
        data = self._read_chart(c)
        self.assertEqual(data['summary'], {'value': 10})

    def test_read_summary_not_aggregate(self):
        m = self._create_object_metric(name='summary_hidden')
        c = self._create_chart(metric=m)
        data = self._read_chart(c)
        self.assertEqual(data['summary'], {'value': None})

    def test_read_summary_top_fields(self):
        m = self._create_object_metric(
            name='applications', configuration='top_fields_mean'
        )
        c = self._create_chart(
            metric=m, test_data=False, configuration='top_fields_mean'
        )
        m.write(
            0,
            extra_values={
                'google': 150.00000001,
                'facebook': 0.00911111,
                'reddit': 0.0,
            },
            time=now() - timedelta(days=2),
        )
        m.write(
            0,
            extra_values={
                'google': 200.00000001,
                'facebook': 0.00611111,
                'reddit': 0.0,
            },
            time=now() - timedelta(days=1),
        )
        m.write(
            0,
            extra_values={
                'google': 250.00000001,
                'facebook': 0.00311111,
                'reddit': 0.0,
            },
            time=now() - timedelta(days=0),
        )
        data = self._read_chart(c)
        self.assertEqual(data['summary'], {'google': 200.0, 'facebook': 0.0061})

    def test_read_summary_top_fields_acid(self):
        m = self._create_object_metric(
            name='applications', configuration='top_fields_mean'
        )
        c = self._create_chart(
            metric=m, test_data=False, configuration='top_fields_mean'
        )
        m.write(
            0,
            extra_values={'google': 0.0, 'facebook': 6000.0, 'reddit': 0.0},
            time=now() - timedelta(days=3),
        )
        m.write(
            0,
            extra_values={
                'google': 150000000.0,
                'facebook': 90000000.0,
                'reddit': 1000.0,
            },
            time=now() - timedelta(days=2),
        )
        m.write(
            0,
            extra_values={'google': 200000000.0, 'facebook': 60000000.0, 'reddit': 0.0},
            time=now() - timedelta(days=1),
        )
        m.write(
            0,
            extra_values={'google': 0.0, 'facebook': 6000.0, 'reddit': 0.0},
            time=now() - timedelta(days=0),
        )
        data = self._read_chart(c)
        self.assertEqual(data['summary'], {'google': 87500000, 'facebook': 37503000})
        self.assertEqual(c.get_top_fields(2), ['google', 'facebook'])

    def test_read_multiple(self):
        c = self._create_chart(test_data=None, configuration='multiple_test')
        m1 = c.metric
        m2 = self._create_object_metric(
            name='test metric 2',
            key='test_metric',
            field_name='value2',
            content_object=m1.content_object,
        )
        now_ = now()
        for n in range(0, 3):
            time = now_ - timedelta(days=n)
            m1.write(n + 1, time=time)
            m2.write(n + 2, time=time)
        data = self._read_chart(c)
        f1 = m1.field_name
        f2 = 'value2'
        self.assertIn('x', data)
        self.assertIn('traces', data)
        self.assertEqual(len(data['x']), 3)
        charts = data['traces']
        self.assertIn(f1, charts[0][0])
        self.assertIn(f2, charts[1][0])
        self.assertEqual(len(charts[0][1]), 3)
        self.assertEqual(len(charts[1][1]), 3)
        self.assertEqual(charts[0][1], [3, 2, 1])
        self.assertEqual(charts[1][1], [4, 3, 2])

    def test_read_group_by_tag(self):
        m1 = self._create_object_metric(
            name='test metric 1',
            key='test_metric',
            field_name='item',
            extra_tags={'metric_num': 'first'},
        )
        m2 = self._create_object_metric(
            name='test metric 2',
            key='test_metric',
            field_name='item',
            content_object=self._create_org(),
            extra_tags={'metric_num': 'second'},
        )
        c = self._create_chart(metric=m1, test_data=False, configuration='group_by_tag')
        now_ = now()
        for n in range(0, 3):
            time = now_ - timedelta(days=n)
            m1.write(n + 1, time=time)
            m2.write(n + 2, time=time)
        data = self._read_chart(c, time='30d', start_date=time)
        self.assertIn('x', data)
        self.assertIn('traces', data)
        self.assertEqual(len(data['x']), 3)
        charts = data['traces']
        self.assertIn('first', charts[0][0])
        self.assertIn('second', charts[1][0])
        self.assertEqual(len(charts[0][1]), 3)
        self.assertEqual(len(charts[1][1]), 3)
        self.assertEqual(charts[0][1], [3, 5, 6])
        self.assertEqual(charts[1][1], [4, 7, 9])
        self.assertEqual(data['summary']['first'], 6)
        self.assertEqual(data['summary']['second'], 9)

    def test_json(self):
        c = self._create_chart()
        data = self._read_chart(c)
        # convert tuples to lists otherwise comparison will fail
        for i, chart in enumerate(data['traces']):
            data['traces'][i] = list(chart)
        # update data with unit
        data.update(
            {
                'unit': c.unit,
                'trace_type': c.trace_type,
                'trace_order': c.trace_order,
                'calculate_total': False,
                'connect_points': c.connect_points,
                'colors': c.colors,
            }
        )
        self.assertDictEqual(json.loads(c.json()), data)

    def test_read_bad_query(self):
        try:
            self._create_chart(configuration='bad_test')
        except ValidationError as e:
            self.assertIn('configuration', e.message_dict)
            self.assertIn('error parsing query: found BAD', str(e.message_dict))
        else:
            self.fail('ValidationError not raised')

    def test_get_query(self):
        c = self._create_chart(test_data=False)
        m = c.metric
        now_ = now()
        today = date(now_.year, now_.month, now_.day)
        time = today - timedelta(days=6)
        expected = c.query.format(
            field_name=m.field_name,
            key=m.key,
            content_type=m.content_type_key,
            object_id=m.object_id,
            time=str(time),
            end_date='',
        )
        expected = "{0} tz('{1}')".format(expected, settings.TIME_ZONE)
        self.assertEqual(c.get_query(), expected)

    def test_description(self):
        c = self._create_chart(test_data=False)
        self.assertEqual(c.description, 'Dummy chart for testing purposes.')

    def test_wifi_hostapd(self):
        m = self._create_object_metric(
            name='wifi associations',
            key='hostapd',
            field_name='mac',
            extra_tags={'ifname': 'wlan0'},
        )
        c = self._create_chart(metric=m, test_data=False, configuration='wifi_clients')
        now_ = now()
        for n in range(0, 9):
            m.write('00:16:3e:00:00:00', time=now_ - timedelta(days=n))
            m.write('00:23:4b:00:00:00', time=now_ - timedelta(days=n, seconds=1))
        m.write('00:16:3e:00:00:00', time=now_ - timedelta(days=2))
        m.write('00:16:3e:00:00:00', time=now_ - timedelta(days=4))
        m.write('00:23:4a:00:00:00')
        m.write('00:14:5c:00:00:00')
        c.save()
        data = self._read_chart(c, time='30d')
        self.assertEqual(data['traces'][0][0], 'wifi_clients')
        # last 10 days
        self.assertEqual(data['traces'][0][1][-10:], [0, 2, 2, 2, 2, 2, 2, 2, 2, 4])

    def test_get_time(self):
        c = Chart()
        now_ = now()
        today = date(now_.year, now_.month, now_.day)
        self.assertIn(str(today - timedelta(days=30)), c._get_time('30d'))
        self.assertIn(str(now() - timedelta(days=1))[0:10], c._get_time('1d'))
        self.assertIn(str(now() - timedelta(days=3))[0:10], c._get_time('3d'))

    def test_get_top_fields(self):
        m = self._create_object_metric(name='test', configuration='get_top_fields')
        c = self._create_chart(metric=m, test_data=None, configuration='histogram')
        self.assertEqual(c.get_top_fields(number=3), [])
        self._write_metric(
            m, None, extra_values={'http2': 100, 'ssh': 90, 'udp': 80, 'spdy': 70}
        )
        self.assertEqual(c.get_top_fields(number=3), ['http2', 'ssh', 'udp'])

    def test_query_histogram(self):
        m = self._create_object_metric(name='histogram', configuration='get_top_fields')
        self._write_metric(
            m, None, extra_values={'http2': 100, 'ssh': 90, 'udp': 80, 'spdy': 70}
        )
        c = Chart(metric=m, configuration='histogram')
        c.full_clean()
        c.save()
        self.assertNotIn('GROUP BY time', c.get_query())

    @capture_stderr()
    def test_bad_json_query_returns_none(self):
        m = self._create_object_metric(
            name='wifi associations',
            key='hostapd',
            field_name='mac',
            extra_tags={'ifname': 'wlan0'},
        )
        c = self._create_chart(metric=m, test_data=False, configuration='wifi_clients')
        m.write('00:14:5c:00:00:00')
        c.save()
        self.assertIsNone(c.json(time=1))

    def test_register_invalid_chart_configuration(self):
        with self.subTest('Registering with incomplete chart configuration.'):
            with self.assertRaises(AssertionError):
                register_chart('test_type', dict())
        with self.subTest('Registering already registered chart configuration.'):
            histogram = charts['histogram']
            register_chart('histogram_test', histogram)
            with self.assertRaises(ImproperlyConfigured):
                register_chart('histogram_test', histogram)
            unregister_chart('histogram_test')
        with self.subTest('Registering with improper chart configuration name'):
            with self.assertRaises(ImproperlyConfigured):
                register_chart(['test_type'], dict())
        with self.subTest('Registering with improper chart configuration'):
            with self.assertRaises(ImproperlyConfigured):
                register_chart('test_type', tuple())

    def test_unregister_invalid_chart_configuration(self):
        with self.subTest('Unregistering with improper chart configuration name'):
            with self.assertRaises(ImproperlyConfigured):
                unregister_chart(dict())
        with self.subTest('Unregistering unregistered chart configuration'):
            with self.assertRaises(ImproperlyConfigured):
                unregister_chart('test_chart')

    def test_register_valid_chart_configuration(self):
        dummy = charts['dummy']
        register_chart('dummy_test', dummy)
        self.assertIn(('dummy_test', 'dummy_test'), CHART_CONFIGURATION_CHOICES)
        unregister_chart('dummy_test')
        self.assertNotIn(('dummy_test', 'dummy_test'), CHART_CONFIGURATION_CHOICES)

    def test_additional_charts_setting(self):
        self.assertNotIn('dummy_test', get_chart_configuration())
        chart = {'dummy_test': charts['dummy']}
        with patch.object(app_settings, 'ADDITIONAL_CHARTS', chart):
            self.assertEqual(
                get_chart_configuration()['dummy_test'], chart['dummy_test']
            )

    def test_clean_dashboard_traffic_chart(self):
        with self.subTest('Test default dashboard traffic chart interfaces'):
            self.assertDictEqual(
                DEFAULT_DASHBOARD_TRAFFIC_CHART, {'__all__': ['wan', 'eth1', 'eth0_2']}
            )
