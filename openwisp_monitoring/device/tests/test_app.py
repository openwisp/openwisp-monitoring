from django.test import TestCase

from openwisp_utils.admin_theme.dashboard import DASHBOARD_CONFIG


class TestCustomAdminDashboard(TestCase):
    def test_monitoring_status_graph_registered(self):
        expected_config = {
            'name': 'Monitoring Status',
            'query_params': {
                'app_label': 'config',
                'model': 'device',
                'group_by': 'monitoring__status',
            },
            'colors': {
                'unknown': 'grey',
                'ok': 'green',
                'critical': 'orange',
                'problem': 'red',
            },
        }

        element_config = DASHBOARD_CONFIG.get(0, None)
        self.assertNotEqual(element_config, None)
        self.assertDictEqual(element_config, expected_config)
