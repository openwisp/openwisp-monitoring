from django.test import TestCase
from django.urls import reverse
from swapper import load_model

from openwisp_controller.config.tests.utils import CreateConfigTemplateMixin

from . import TestMonitoringMixin

Organization = load_model('openwisp_users', 'Organization')
Metric = load_model('monitoring', 'Metric')
OrganizationUser = load_model('openwisp_users', 'OrganizationUser')
Group = load_model('openwisp_users', 'Group')


class TestDashboardTimeseriesView(
    CreateConfigTemplateMixin, TestMonitoringMixin, TestCase
):
    def setUp(self):
        super().setUp()

    def _test_response_data(self, response):
        self.assertIn('x', response.data)
        charts = response.data['charts']
        for chart in charts:
            self.assertIn('traces', chart)
            self.assertIn('title', chart)
            self.assertIn('description', chart)
            self.assertIn('type', chart)
            self.assertIn('summary', chart)
            self.assertIsInstance(chart['summary'], dict)
            self.assertIn('summary_labels', chart)
            self.assertIsInstance(chart['summary_labels'], list)
            self.assertIn('unit', chart)
            self.assertIn('colors', chart)
            self.assertIn('colorscale', chart)

    def test_wifi_client_chart(self):
        def _test_chart_properties(chart):
            self.assertEqual(chart['title'], 'WiFi clients')
            self.assertEqual(chart['type'], 'bar')
            self.assertEqual(chart['unit'], '')
            self.assertEqual(chart['summary_labels'], ['Total Unique WiFi clients'])
            self.assertEqual(chart['colors'], ['#1f77b4'])
            self.assertEqual(chart['colorscale'], None)
            self.assertEqual(
                chart['description'],
                'WiFi clients associated to the wireless interface.',
            )

        def _create_org_wifi_client_metric(org):
            return self._create_general_metric(
                name='wifi_clients',
                configuration='clients',
                field_name='clients',
                main_tags={'ifname': 'wlan0'},
                extra_tags={'organization_id': str(org.id)},
            )

        path = reverse('monitoring:api_dashboard_timeseries')
        org1 = self._create_org(name='org1', slug='org1')
        org2 = self._create_org(name='org2', slug='org2')
        org3 = self._create_org(name='org3', slug='org3')
        org1_metric = _create_org_wifi_client_metric(org1)
        org2_metric = _create_org_wifi_client_metric(org2)
        org3_metric = _create_org_wifi_client_metric(org3)

        org1_metric.write('00:23:4a:00:00:00')
        org2_metric.write('00:23:4b:00:00:00')
        org3_metric.write('00:14:5c:00:00:00')

        admin = self._create_admin()
        org2_administrator = self._create_user()
        OrganizationUser.objects.create(
            user=org2_administrator, organization=org2, is_admin=True
        )
        OrganizationUser.objects.create(
            user=org2_administrator, organization=org3, is_admin=True
        )
        groups = Group.objects.filter(name='Administrator')
        org2_administrator.groups.set(groups)
        operator = self._create_operator()

        self.client.force_login(admin)
        with self.subTest('Test superuser retrieves metric for all organizations'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self._test_response_data(response)
            chart = response.data['charts'][0]
            self.assertEqual(chart['traces'][0][1][-1], 3)
            self.assertEqual(chart['summary']['wifi_clients'], 3)
            _test_chart_properties(chart)

        with self.subTest('Test superuser retrieves metric for one organization'):
            response = self.client.get(path, {'organization_slug': org2.slug})
            self.assertEqual(response.status_code, 200)
            self._test_response_data(response)
            chart = response.data['charts'][0]
            self.assertEqual(chart['traces'][0][1][-1], 1)
            self.assertEqual(chart['summary']['wifi_clients'], 1)
            _test_chart_properties(chart)

        with self.subTest('Test superuser retrieves metric for multiple organization'):
            response = self.client.get(
                path, {'organization_slug': f'{org1.slug},{org2.slug}'}
            )
            self.assertEqual(response.status_code, 200)
            self._test_response_data(response)
            chart = response.data['charts'][0]
            self.assertEqual(chart['traces'][0][1][-1], 2)
            self.assertEqual(chart['summary']['wifi_clients'], 2)
            _test_chart_properties(chart)

        self.client.force_login(org2_administrator)
        with self.subTest(
            'Test org admin retrieves metrics for their managed organization'
        ):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self._test_response_data(response)
            chart = response.data['charts'][0]
            self.assertEqual(chart['traces'][0][1][-1], 2)
            self.assertEqual(chart['summary']['wifi_clients'], 2)
            _test_chart_properties(chart)

        with self.subTest(
            'Test org admin retrieves metrics for one managed organizations'
        ):
            response = self.client.get(path, {'organization_slug': org2.slug})
            self.assertEqual(response.status_code, 200)
            self._test_response_data(response)
            chart = response.data['charts'][0]
            self.assertEqual(chart['traces'][0][1][-1], 1)
            self.assertEqual(chart['summary']['wifi_clients'], 1)
            _test_chart_properties(chart)

        with self.subTest(
            'Test org admin retrieves metrics for multiple managed organizations'
        ):
            response = self.client.get(
                path, {'organization_slug': f'{org2.slug},{org3.slug}'}
            )
            self.assertEqual(response.status_code, 200)
            self._test_response_data(response)
            chart = response.data['charts'][0]
            self.assertEqual(chart['traces'][0][1][-1], 2)
            self.assertEqual(chart['summary']['wifi_clients'], 2)
            _test_chart_properties(chart)

        with self.subTest('Test org admin retrieve metrics for unmanaged organization'):
            response = self.client.get(path, {'organization_slug': f'{org1.slug}'})
            self.assertEqual(response.status_code, 403)

        with self.subTest(
            'Test org admin retrieve metrics for multiple organizations (unmanaged org included)'
        ):
            response = self.client.get(
                path, {'organization_slug': f'{org1.slug},{org2.slug}'}
            )
            self.assertEqual(response.status_code, 403)

        with self.subTest('Test filtering for non-existing organization'):
            response = self.client.get(path, {'organization_slug': 'non-existing-org'})
            self.assertEqual(response.status_code, 404)

        self.client.force_login(operator)
        with self.subTest('Test non-org admin retrieve metric'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 403)
