from unittest.mock import patch

from django.urls import reverse
from openwisp_notifications.signals import notify
from swapper import load_model

from openwisp_controller.config.signals import config_status_changed
from openwisp_controller.connection.tests.base import CreateConnectionsMixin
from openwisp_utils.tests import catch_signal

from ...check.classes import Ping
from ...check.tests import _FPING_REACHABLE, _FPING_UNREACHABLE
from ..tasks import trigger_device_checks
from . import DeviceMonitoringTransactionTestcase

Check = load_model('check', 'Check')
DeviceMonitoring = load_model('device_monitoring', 'DeviceMonitoring')
DeviceConnection = load_model('connection', 'DeviceConnection')
Credentials = load_model('connection', 'Credentials')
Check = load_model('check', 'Check')


class TestTransactions(CreateConnectionsMixin, DeviceMonitoringTransactionTestcase):
    def _delete_non_ping_checks(self):
        Check.objects.exclude(name='Ping').delete()
        self.assertEqual(Check.objects.count(), 1)

    @patch('openwisp_monitoring.check.tasks.perform_check.delay')
    def test_config_status_changed_receiver(self, mock_method):
        c = self._create_config(status='applied', organization=self._create_org())
        c.config = {'general': {'description': 'test'}}
        c.full_clean()
        with catch_signal(config_status_changed) as handler:
            c.save()
            handler.assert_called_once()
        self.assertEqual(c.status, 'modified')
        self.assertEqual(mock_method.call_count, 1)

    @patch.object(Ping, '_command', return_value=_FPING_REACHABLE)
    def test_trigger_device_recovery_task(self, mocked_method):
        d = self._create_device(organization=self._create_org())
        d.management_ip = '10.40.0.5'
        d.save()
        data = self._data()
        # Creation of resources, clients and traffic metrics can be avoided here
        # as they are not involved. This speeds up the test by reducing requests made.
        del data['resources']
        del data['interfaces']
        self._delete_non_ping_checks()
        d.monitoring.update_status('critical')
        url = reverse('monitoring:api_device_metric', args=[d.pk.hex])
        url = '{0}?key={1}'.format(url, d.key)
        with patch.object(Check, 'perform_check') as mock:
            self._post_data(d.id, d.key, data)
            mock.assert_called_once()

    @patch.object(Ping, '_command', return_value=_FPING_UNREACHABLE)
    @patch.object(DeviceMonitoring, 'update_status')
    def test_trigger_device_recovery_task_regression(
        self, mocked_update_status, mocked_ping
    ):
        dm = self._create_device_monitoring()
        dm.device.management_ip = None
        dm.device.save()
        trigger_device_checks.delay(dm.device.pk)
        self.assertTrue(Check.objects.exists())
        # we expect update_status() to be called once (by the check)
        # and not a second time directly by our code
        mocked_update_status.assert_called_once()

    @patch.object(Check, 'perform_check')
    def test_is_working_false_true(self, perform_check):
        d = self._create_device()
        dm = d.monitoring
        dm.status = 'unknown'
        dm.save()
        self._delete_non_ping_checks()
        c = Credentials.objects.create()
        dc = DeviceConnection.objects.create(credentials=c, device=d, is_working=False)
        self.assertFalse(dc.is_working)
        dc.is_working = True
        dc.save()
        perform_check.assert_called_once()

    @patch.object(Check, 'perform_check')
    def test_is_working_changed_to_false(self, perform_check):
        d = self._create_device()
        dm = d.monitoring
        dm.status = 'ok'
        dm.save()
        self._delete_non_ping_checks()
        c = Credentials.objects.create()
        dc = DeviceConnection.objects.create(credentials=c, device=d)
        dc.is_working = False
        dc.save()
        perform_check.assert_called_once()

    @patch.object(Check, 'perform_check')
    @patch.object(notify, 'send')
    def test_is_working_none_true(self, notify_send, perform_check):
        d = self._create_device()
        dm = d.monitoring
        dm.status = 'unknown'
        dm.save()
        self._delete_non_ping_checks()
        c = Credentials.objects.create()
        dc = DeviceConnection.objects.create(credentials=c, device=d)
        self.assertIsNone(dc.is_working)
        dc.is_working = True
        dc.save()
        notify_send.assert_not_called()
        perform_check.assert_not_called()

    @patch.object(Check, 'perform_check')
    @patch.object(notify, 'send')
    def test_is_working_changed_unable_to_connect(self, notify_send, perform_check):
        ckey = self._create_credentials_with_key(port=self.ssh_server.port)
        dc = self._create_device_connection(credentials=ckey)
        dc.is_working = True
        dc.save()
        notify_send.assert_not_called()
        perform_check.assert_not_called()

        d = self.device_model.objects.first()
        d.monitoring.update_status('ok')
        self._delete_non_ping_checks()
        dc.is_working = False
        dc.failure_reason = '[Errno None] Unable to connect to port 5555 on 127.0.0.1'
        dc.full_clean()
        dc.save()
        perform_check.assert_not_called()

    @patch.object(Check, 'perform_check')
    @patch.object(notify, 'send')
    def test_is_working_changed_timed_out(self, notify_send, perform_check):
        ckey = self._create_credentials_with_key(port=self.ssh_server.port)
        dc = self._create_device_connection(credentials=ckey, is_working=None)
        self.assertIsNone(dc.is_working)
        dc.is_working = True
        dc.save()
        perform_check.assert_not_called()

        d = self.device_model.objects.first()
        d.monitoring.update_status('ok')
        self._delete_non_ping_checks()
        dc.is_working = False
        dc.failure_reason = 'timed out'
        dc.full_clean()
        dc.save()
        perform_check.assert_not_called()

    @patch.object(Check, 'perform_check')
    @patch.object(notify, 'send')
    def test_is_working_no_recovery_notification(self, notify_send, perform_check):
        ckey = self._create_credentials_with_key(port=self.ssh_server.port)
        dc = self._create_device_connection(credentials=ckey, is_working=True)
        d = self.device_model.objects.first()
        d.monitoring.update_status('ok')
        dc.refresh_from_db()
        self._delete_non_ping_checks()
        failure_reason = '[Errno None] Unable to connect to port 5555 on 127.0.0.1'
        self.assertTrue(dc.is_working)
        dc.failure_reason = failure_reason
        dc.is_working = False
        dc.save()
        # Recovery is made
        dc.failure_reason = ''
        dc.is_working = True
        dc.save()
        perform_check.assert_not_called()
