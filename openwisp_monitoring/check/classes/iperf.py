from swapper import load_model

from .base import BaseCheck

Chart = load_model('monitoring', 'Chart')
Metric = load_model('monitoring', 'Metric')
Device = load_model('config', 'Device')
DeviceData = load_model('device_monitoring', 'DeviceData')
Credentials = load_model('connection', 'Credentials')
AlertSettings = load_model('monitoring', 'AlertSettings')
DeviceConnection = load_model('connection', 'DeviceConnection')


class Iperf(BaseCheck):
    def check(self, store=True):
        pass

    def store_result(self, result):
        """
        store result in the DB
        """
        pass

    def _get_iperf_servers(self):
        """
        Get iperf test servers
        """
        pass

    def _get_iperf_result(self, mode=None):
        """
        Get iperf test result
        """
        pass

    def _get_metric(self):
        """
        Gets or creates metric
        """
        pass

    def _create_charts(self, metric):
        """
        Creates iperf related charts (Bandwith/Jitter)
        """
        pass

    def _create_alert_settings(self, metric):
        pass
