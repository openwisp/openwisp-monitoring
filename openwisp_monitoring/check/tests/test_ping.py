from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TransactionTestCase
from swapper import load_model

from ... import settings as monitoring_settings
from ...device.tests import TestDeviceMonitoringMixin
from .. import settings
from ..classes import Ping
from ..classes.ping import get_ping_schema
from ..exceptions import OperationalError
from . import _FPING_REACHABLE, _FPING_UNREACHABLE

Chart = load_model('monitoring', 'Chart')
AlertSettings = load_model('monitoring', 'AlertSettings')
Metric = load_model('monitoring', 'Metric')
Check = load_model('check', 'Check')


class TestPing(TestDeviceMonitoringMixin, TransactionTestCase):
    _PING = settings.CHECK_CLASSES[0][0]
    _RESULT_KEYS = ['reachable', 'loss', 'rtt_min', 'rtt_avg', 'rtt_max']
    _RTT_KEYS = _RESULT_KEYS[-3:]
    _UNRECOGNIZED_OUTPUT = (
        '',
        bytes("fping: option requires an argument -- 'z'", encoding='utf8'),
    )

    @patch.object(Ping, '_command', return_value=_FPING_REACHABLE)
    def test_check_ping_no_params(self, mocked_method):
        device = self._create_device(organization=self._create_org())
        # will ping localhost
        device.management_ip = '127.0.0.1'
        check = Check(
            name='Ping check', check_type=self._PING, content_object=device, params={}
        )
        result = check.perform_check(store=False)
        for key in self._RESULT_KEYS:
            self.assertIn(key, result)
        self.assertEqual(result['reachable'], 1)
        self.assertEqual(result['loss'], 0.0)
        for key in self._RTT_KEYS:
            self.assertTrue(result[key] < 1)

    def test_check_ping_params(self):
        device = self._create_device(organization=self._create_org())
        # will ping localhost
        device.management_ip = '127.0.0.1'
        check = Check(
            name='Ping check',
            check_type=self._PING,
            content_object=device,
            params={'count': 2, 'interval': 10, 'bytes': 12, 'timeout': 50},
        )
        result = check.perform_check(store=False)
        for key in self._RESULT_KEYS:
            self.assertIn(key, result)
        self.assertEqual(result['reachable'], 1)
        self.assertEqual(result['loss'], 0.0)
        for key in self._RTT_KEYS:
            self.assertTrue(result[key] < 1)

    @patch.object(
        settings,
        'PING_CHECK_CONFIG',
        {
            'timeout': {'default': '10000'},
            'count': {'default': 22},
            'bytes': {'default': 1024},
        },
    )
    def test_ping_check_config(self, *args):
        with patch.object(Ping, 'schema', get_ping_schema()):
            device = self._create_device(organization=self._create_org())
            # will ping localhost
            device.management_ip = '127.0.0.1'
            check = Check(
                name='Ping check',
                check_type=self._PING,
                content_object=device,
                params={},
            )
            with patch.object(
                Ping, '_command', return_value=_FPING_REACHABLE
            ) as mocked_command:
                check.perform_check(store=False)
            mocked_command.assert_called_once_with(
                [
                    'fping',
                    '-e',
                    '-c 22',
                    '-p 25',
                    '-b 1024',
                    '-t 10000',
                    '-q',
                    '127.0.0.1',
                ]
            )

    @patch.object(Ping, '_command', return_value=_FPING_UNREACHABLE)
    def test_check_ping_unreachable(self, mocked_method):
        device = self._create_device(organization=self._create_org())
        device.management_ip = '192.168.255.255'
        check = Check(
            name='Ping check',
            check_type=self._PING,
            content_object=device,
            params={'timeout': 50, 'count': 3},
        )
        result = check.perform_check(store=False)
        for key in self._RESULT_KEYS[0:2]:
            self.assertIn(key, result)
        self.assertFalse(result['reachable'], 0)
        self.assertEqual(result['loss'], 100.0)

    @patch.object(Ping, '_command', return_value=_UNRECOGNIZED_OUTPUT)
    def test_operational_error(self, _command):
        device = self._create_device(organization=self._create_org())
        device.management_ip = '127.0.0.1'
        check = Check(
            name='Ping check',
            check_type=self._PING,
            content_object=device,
            params={'timeout': 50, 'count': 3},
        )
        try:
            check.perform_check(store=False)
        except OperationalError as e:
            self.assertIn('Unrecognized fping output:', str(e))
        else:
            self.fail('OperationalError not raised')

    @patch.object(Ping, '_command', return_value=_FPING_REACHABLE)
    def _check_no_ip_case(self, status, mocked_method, management_ip_only=False):
        device = self._create_device(
            organization=self._create_org(), last_ip='127.0.0.1'
        )
        device.monitoring.update_status(status)
        check = Check(
            name='Ping check', check_type=self._PING, content_object=device, params={}
        )
        result = check.perform_check(store=True)
        if not management_ip_only:
            if status != 'unknown':
                expected_result = {'reachable': 0, 'loss': 100}
                expected_status = 'critical'
                expected_metrics_count = 1
            else:
                expected_result = None
                expected_status = status
                expected_metrics_count = 0
            self.assertEqual(result, expected_result)
        else:
            expected_status = 'ok'
            expected_metrics_count = 1
        device.monitoring.refresh_from_db()
        self.assertEqual(device.monitoring.status, expected_status)
        self.assertEqual(Metric.objects.count(), expected_metrics_count)

    @patch.object(Ping, '_command', return_value=_FPING_REACHABLE)
    @patch('openwisp_monitoring.check.settings.MANAGEMENT_IP_ONLY', True)
    def test_device_without_ip_unknown_status(self, mocked_method):
        self._check_no_ip_case('unknown')

    @patch.object(Ping, '_command', return_value=_FPING_REACHABLE)
    @patch('openwisp_monitoring.check.settings.MANAGEMENT_IP_ONLY', True)
    def test_device_without_ip_ok_status(self, mocked_method):
        self._check_no_ip_case('ok')

    @patch.object(Ping, '_command', return_value=_FPING_REACHABLE)
    @patch('openwisp_monitoring.check.settings.MANAGEMENT_IP_ONLY', True)
    def test_device_without_ip_problem_status(self, mocked_method):
        self._check_no_ip_case('problem')

    @patch.object(Ping, '_command', return_value=_FPING_REACHABLE)
    @patch('openwisp_monitoring.check.settings.MANAGEMENT_IP_ONLY', True)
    def test_device_without_ip_critical_status(self, mocked_method):
        self._check_no_ip_case('critical')

    @patch.object(Ping, '_command', return_value=_FPING_REACHABLE)
    @patch('openwisp_monitoring.check.settings.MANAGEMENT_IP_ONLY', False)
    def test_device_with_last_ip_unknown_status(self, mocked_method):
        self._check_no_ip_case('unknown', management_ip_only=True)

    def test_content_object_none(self):
        check = Check(name='Ping check', check_type=self._PING, params={})
        try:
            check.check_instance.validate()
        except ValidationError as e:
            self.assertIn('device', str(e))
        else:
            self.fail('ValidationError not raised')

    def test_content_object_not_device(self):
        check = Check(
            name='Ping check',
            check_type=self._PING,
            content_object=self._create_user(),
            params={},
        )
        try:
            check.check_instance.validate()
        except ValidationError as e:
            self.assertIn('device', str(e))
        else:
            self.fail('ValidationError not raised')

    def test_schema_violation(self):
        device = self._create_device(organization=self._create_org())
        device.management_ip = '127.0.0.1'
        invalid_params = [
            {'count': 1},
            {'interval': 9},
            {'bytes': 0},
            {'timeout': 2},
            {'count': 'ciao'},
            {'wrong': True},
            {'bytes': 999999, 'count': 99},
        ]
        for params in invalid_params:
            check = Check(
                name='Ping check',
                check_type=self._PING,
                content_object=device,
                params=params,
            )
            try:
                check.check_instance.validate()
            except ValidationError as e:
                self.assertIn('Invalid param', str(e))
            else:
                self.fail('ValidationError not raised')

    @patch.object(Ping, '_command', return_value=_FPING_REACHABLE)
    def test_store_result(self, mocked_method):
        self.assertEqual(Check.objects.count(), 0)
        device = self._create_device(organization=self._create_org())
        device.management_ip = '10.40.0.1'
        device.save()
        # check created automatically by autoping
        self.assertEqual(Check.objects.count(), 3)
        self.assertEqual(Metric.objects.count(), 0)
        self.assertEqual(Chart.objects.count(), 0)
        self.assertEqual(AlertSettings.objects.count(), 0)
        check = Check.objects.filter(check_type=self._PING).first()
        result = check.perform_check()
        self.assertEqual(Metric.objects.count(), 1)
        self.assertEqual(Chart.objects.count(), 3)
        self.assertEqual(AlertSettings.objects.count(), 1)
        m = Metric.objects.first()
        self.assertEqual(m.content_object, device)
        self.assertEqual(m.key, 'ping')
        points = self._read_metric(m, limit=None, extra_fields=list(result.keys()))
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0]['reachable'], result['reachable'])
        self.assertEqual(points[0]['loss'], result['loss'])
        self.assertEqual(points[0]['rtt_min'], result['rtt_min'])
        self.assertEqual(points[0]['rtt_avg'], result['rtt_avg'])
        self.assertEqual(points[0]['rtt_max'], result['rtt_max'])

    @patch.object(Ping, '_command', return_value=_FPING_REACHABLE)
    @patch.object(monitoring_settings, 'AUTO_CHARTS', return_value=[])
    def test_auto_chart_disabled(self, *args):
        device = self._create_device(organization=self._create_org())
        device.last_ip = '127.0.0.1'
        device.save()
        check = Check.objects.first()
        self.assertEqual(Chart.objects.count(), 0)
        check.perform_check()
        self.assertEqual(Chart.objects.count(), 0)
