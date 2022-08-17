from django.test import TestCase

from openwisp_utils.admin_theme.dashboard import DASHBOARD_CHARTS, DASHBOARD_TEMPLATES


class TestApps(TestCase):
    def test_monitoring_status_chart_registered(self):
        chart_config = DASHBOARD_CHARTS.get(0, None)
        self.assertIsNotNone(chart_config)
        self.assertEqual(chart_config['name'], 'Monitoring Status')
        self.assertIn('labels', chart_config)
        self.assertNotIn('filters', chart_config)
        query_params = chart_config['query_params']
        self.assertIn('group_by', query_params)
        self.assertEqual(query_params['group_by'], 'monitoring__status')

    def test_device_map_template_registered(self):
        template_config = DASHBOARD_TEMPLATES.get(0, None)
        self.assertIsNotNone(template_config)
        self.assertEqual(
            template_config[0]['template'], 'admin/dashboard/device_map.html'
        )
        self.assertEqual(
            template_config[0].get('css'),
            (
                'monitoring/css/device-map.css',
                'leaflet/leaflet.css',
                'monitoring/css/leaflet.fullscreen.css',
                'monitoring/css/netjsongraph.css',
            ),
        )
        self.assertEqual(
            template_config[0].get('js'),
            (
                'monitoring/js/lib/netjsongraph.min.js',
                'monitoring/js/lib/leaflet.fullscreen.min.js',
                'monitoring/js/device-map.js',
            ),
        )
