from django.test import TestCase

from openwisp_monitoring.device.models import CHECK_CLASSES, Check
from openwisp_monitoring.device.signals import health_status_changed
from openwisp_utils.admin_theme.dashboard import DASHBOARD_CHARTS, DASHBOARD_TEMPLATES
from openwisp_utils.tests import catch_signal


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


class TestCheckSignals(TestCase):
    def setUp(self):
        self.device = self._create_device(organization=self._create_org())
        self.ping_check = Check.objects.create(
            name='Ping Check',
            check_type=CHECK_CLASSES[0][0],
            content_object=self.device,
            params={},
        )
        self.device.monitoring.update_status('ok')

    def test_check_signals(self):
        with self.subTest('Test disabling a critical check'):
            self.assertEqual(self.device.monitoring.status, 'ok')
            with catch_signal(health_status_changed) as handler:
                self.ping_check.is_active = False
                self.ping_check.save()
            self.assertEqual(handler.call_count, 1)
            call_args = handler.call_args[0]
            self.assertEqual(call_args[0], self.device.monitoring)
            self.assertEqual(call_args[1], 'unknown')
            self.device.refresh_from_db()
            self.assertEqual(self.device.monitoring.status, 'unknown')
            self.device.monitoring.update_status('ok')

        with self.subTest('Test saving an active critical check'):
            self.assertEqual(self.device.monitoring.status, 'ok')
            self.ping_check.is_active = True
            self.ping_check.save()
            self.device.refresh_from_db()
            self.assertEqual(self.device.monitoring.status, 'ok')

        with self.subTest('Test saving a non-critical check'):
            self.assertEqual(self.device.monitoring.status, 'ok')
            non_critical_check = Check.objects.create(
                name='Configuration Applied',
                check_type=CHECK_CLASSES[1][0],
                content_object=self.device,
                params={},
            )
            non_critical_check.save()
            self.device.refresh_from_db()
            self.assertEqual(self.device.monitoring.status, 'ok')

        with self.subTest('Test deleting a critical check'):
            self.device.monitoring.update_status('ok')
            self.ping_check.delete()
            self.device.refresh_from_db()
            self.assertEqual(self.device.monitoring.status, 'unknown')
