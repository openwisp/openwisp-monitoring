from unittest.mock import patch

from django.test import TransactionTestCase
from swapper import load_model

from openwisp_controller.connection.settings import UPDATE_STRATEGIES
from openwisp_controller.connection.tests.base import CreateConnectionsMixin

from ...device.tests import TestDeviceMonitoringMixin
from .. import settings
from .utils import MockOpenWRT

Check = load_model('check', 'Check')
Credentials = load_model('connection', 'Credentials')


class TestSnmp(CreateConnectionsMixin, TestDeviceMonitoringMixin, TransactionTestCase):
    _SNMPDEVICEMONITORING = settings.CHECK_CLASSES[2][0]

    def test_snmp_perform_check(self):
        device = self._create_device()
        device.management_ip = '192.168.1.1'
        check = Check(check=self._SNMPDEVICEMONITORING, content_object=device)
        with patch(
            'openwisp_monitoring.check.classes.snmp_devicemonitoring.OpenWRT'
        ) as p:
            p.side_effect = MockOpenWRT
            check.perform_check(store=False)
            p.assert_called_once_with(host='192.168.1.1')

    def test_snmp_perform_check_with_credentials(self):
        device = self._create_device()
        device.management_ip = '192.168.1.1'
        check = Check(check=self._SNMPDEVICEMONITORING, content_object=device)
        params = {'community': 'public', 'agent': 'my-agent', 'port': 161}
        cred = self._create_credentials(
            params=params,
            connector='openwisp_controller.connection.connectors.snmp.Snmp',
        )
        self._create_device_connection(
            credentials=cred, device=device, update_strategy=UPDATE_STRATEGIES[1][0]
        )
        with patch(
            'openwisp_monitoring.check.classes.snmp_devicemonitoring.OpenWRT'
        ) as p:
            p.side_effect = MockOpenWRT
            check.perform_check(store=False)
            p.assert_called_once_with(host='192.168.1.1', **params)
