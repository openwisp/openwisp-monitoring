from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from swapper import load_model

from openwisp_controller.config.tests.utils import CreateConfigTemplateMixin
from openwisp_controller.geo.tests.utils import TestGeoMixin

from ..configuration import DEFAULT_DASHBOARD_TRAFFIC_CHART
from . import TestMonitoringMixin

Organization = load_model('openwisp_users', 'Organization')
Metric = load_model('monitoring', 'Metric')
OrganizationUser = load_model('openwisp_users', 'OrganizationUser')
Group = load_model('openwisp_users', 'Group')
DeviceLocation = load_model('geo', 'DeviceLocation')
FloorPlan = load_model('geo', 'FloorPlan')
Location = load_model('geo', 'Location')
Device = load_model('config', 'Device')


class TestDashboardTimeseriesView(
    CreateConfigTemplateMixin, TestMonitoringMixin, TestGeoMixin, TestCase
):
    location_model = Location
    object_location_model = DeviceLocation
    object_model = Device
    floorplan_model = FloorPlan

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

    def _create_org_wifi_client_metric(self, org, **kwargs):
        extra_tags = {'organization_id': str(org.id)}
        extra_tags.update(kwargs)
        return self._create_general_metric(
            name='wifi_clients',
            configuration='general_clients',
            field_name='clients',
            main_tags={'ifname': 'wlan0'},
            extra_tags=extra_tags,
        )

    def _create_org_traffic_metric(self, org, interface_name):
        return self._create_general_metric(
            name='traffic',
            configuration='general_traffic',
            field_name='rx_bytes',
            main_tags={'ifname': interface_name},
            extra_tags={'organization_id': str(org.id)},
        )

    def _create_test_users(self, org):
        admin = self._create_admin()
        org2_administrator = self._create_user()
        OrganizationUser.objects.create(
            user=org2_administrator, organization=org, is_admin=True
        )
        groups = Group.objects.filter(name='Administrator')
        org2_administrator.groups.set(groups)
        operator = self._create_operator()
        return admin, org2_administrator, operator

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

        path = reverse('monitoring_general:api_dashboard_timeseries')
        org1 = self._create_org(name='org1', slug='org1')
        org2 = self._create_org(name='org2', slug='org2')
        org3 = self._create_org(name='org3', slug='org3')
        org1_metric = self._create_org_wifi_client_metric(org1)
        org2_metric = self._create_org_wifi_client_metric(org2)
        org3_metric = self._create_org_wifi_client_metric(org3)

        org1_metric.write('00:23:4a:00:00:00')
        org2_metric.write('00:23:4b:00:00:00')
        org3_metric.write('00:14:5c:00:00:00')

        admin, org2_administrator, operator = self._create_test_users(org2)
        OrganizationUser.objects.create(
            user=org2_administrator, organization=org3, is_admin=True
        )

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

    @patch.dict(
        DEFAULT_DASHBOARD_TRAFFIC_CHART,
        {'__all__': ['wan'], 'org2': ['eth1'], 'org3': ['wan', 'eth1']},
    )
    def test_traffic_chart(self):
        def _test_chart_properties(chart):
            self.assertEqual(chart['title'], 'General Traffic')
            self.assertEqual(chart['type'], 'scatter')
            self.assertEqual(chart['unit'], ' GB')
            self.assertEqual(
                chart['summary_labels'],
                ['Total download traffic', 'Total upload traffic'],
            )
            self.assertEqual(chart['colors'], ['#1f77b4', '#ff7f0e'])
            self.assertEqual(chart['colorscale'], None)
            self.assertEqual(
                chart['description'],
                'Network traffic, download and upload, measured in GB.',
            )

        path = reverse('monitoring_general:api_dashboard_timeseries')
        org1 = self._create_org(name='org1', slug='org1')
        org2 = self._create_org(name='org2', slug='org2')
        org3 = self._create_org(name='org3', slug='org3')
        org1_wan_metric = self._create_org_traffic_metric(org1, 'wan')
        org2_wan_metric = self._create_org_traffic_metric(org2, 'wan')
        org2_eth1_metric = self._create_org_traffic_metric(org2, 'eth1')
        org3_wan_metric = self._create_org_traffic_metric(org3, 'wan')
        org3_eth1_metric = self._create_org_traffic_metric(org3, 'eth1')
        traffic_metrics = {
            'org1': {'wan': 10000000000},
            'org2': {'wan': 20000000000, 'eth1': 60000000000},
            'org3': {'wan': 30000000000, 'eth1': 70000000000},
        }

        org1_wan_metric.write(traffic_metrics['org1']['wan'])
        org2_wan_metric.write(traffic_metrics['org2']['wan'])
        org2_eth1_metric.write(traffic_metrics['org2']['eth1'])
        org3_wan_metric.write(traffic_metrics['org3']['wan'])
        org3_eth1_metric.write(traffic_metrics['org3']['eth1'])

        admin, org2_administrator, operator = self._create_test_users(org2)
        OrganizationUser.objects.create(
            user=org2_administrator, organization=org3, is_admin=True
        )

        self.client.force_login(admin)
        with self.subTest('Test superuser retrieves metric for all organizations'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self._test_response_data(response)
            chart = response.data['charts'][0]
            expected_traffic_data = (
                traffic_metrics['org1']['wan']
                + traffic_metrics['org2']['wan']
                + traffic_metrics['org3']['wan']
            )
            self.assertEqual(
                chart['traces'][0][1][-1], expected_traffic_data / 1000000000
            )
            self.assertEqual(
                chart['summary']['download'], expected_traffic_data / 1000000000
            )
            _test_chart_properties(chart)

        with self.subTest(
            'Test superuser retrieves metric for organization without interface config'
        ):
            response = self.client.get(path, {'organization_slug': org1.slug})
            self.assertEqual(response.status_code, 200)
            self._test_response_data(response)
            chart = response.data['charts'][0]
            self.assertEqual(
                chart['traces'][0][1][-1], traffic_metrics['org1']['wan'] / 1000000000
            )
            self.assertEqual(
                chart['summary']['download'],
                traffic_metrics['org1']['wan'] / 1000000000,
            )
            _test_chart_properties(chart)

        with self.subTest(
            'Test superuser retrieves metric for organization with one interface in config'
        ):
            response = self.client.get(path, {'organization_slug': org2.slug})
            self.assertEqual(response.status_code, 200)
            self._test_response_data(response)
            chart = response.data['charts'][0]
            self.assertEqual(
                chart['traces'][0][1][-1], traffic_metrics['org2']['eth1'] / 1000000000
            )
            self.assertEqual(
                chart['summary']['download'],
                traffic_metrics['org2']['eth1'] / 1000000000,
            )
            _test_chart_properties(chart)

        with self.subTest(
            'Test superuser retrieves metric for organization with multiple interface in config'
        ):
            response = self.client.get(path, {'organization_slug': org3.slug})
            self.assertEqual(response.status_code, 200)
            self._test_response_data(response)
            chart = response.data['charts'][0]
            expected_traffic_data = (
                traffic_metrics['org3']['wan'] + traffic_metrics['org3']['eth1']
            )
            self.assertEqual(
                chart['traces'][0][1][-1], expected_traffic_data / 1000000000
            )
            self.assertEqual(
                chart['summary']['download'], expected_traffic_data / 1000000000
            )
            _test_chart_properties(chart)

        with self.subTest('Test superuser retrieves metric for multiple organization'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self._test_response_data(response)
            chart = response.data['charts'][0]
            expected_traffic_data = (
                traffic_metrics['org1']['wan']
                + traffic_metrics['org2']['wan']
                + traffic_metrics['org3']['wan']
            )
            self.assertEqual(
                chart['traces'][0][1][-1], expected_traffic_data / 1000000000
            )
            self.assertEqual(
                chart['summary']['download'], expected_traffic_data / 1000000000
            )
            _test_chart_properties(chart)

        self.client.force_login(org2_administrator)
        with self.subTest(
            'Test org admin retrieves metrics for their managed organization'
        ):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self._test_response_data(response)
            chart = response.data['charts'][0]
            expected_traffic_data = (
                traffic_metrics['org2']['wan'] + traffic_metrics['org3']['wan']
            )
            self.assertEqual(
                chart['traces'][0][1][-1], expected_traffic_data / 1000000000
            )
            self.assertEqual(
                chart['summary']['download'], expected_traffic_data / 1000000000
            )
            _test_chart_properties(chart)

        with self.subTest(
            'Test org admin retrieves metrics for one managed organizations'
        ):
            response = self.client.get(path, {'organization_slug': org2.slug})
            self.assertEqual(response.status_code, 200)
            self._test_response_data(response)
            chart = response.data['charts'][0]
            self.assertEqual(
                chart['traces'][0][1][-1], traffic_metrics['org2']['eth1'] / 1000000000
            )
            self.assertEqual(
                chart['summary']['download'],
                traffic_metrics['org2']['eth1'] / 1000000000,
            )
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
            expected_traffic_data = (
                traffic_metrics['org2']['wan'] + traffic_metrics['org3']['wan']
            )
            self.assertEqual(
                chart['traces'][0][1][-1], expected_traffic_data / 1000000000
            )
            self.assertEqual(
                chart['summary']['download'], expected_traffic_data / 1000000000
            )
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

        # org2_administrator will only have one managed organization, i.e. org3
        org2.delete()
        with self.subTest(
            'Test org admin retrieves metric for only managed organization'
        ):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self._test_response_data(response)
            chart = response.data['charts'][0]
            expected_traffic_data = (
                traffic_metrics['org3']['wan'] + traffic_metrics['org3']['eth1']
            )
            self.assertEqual(
                chart['traces'][0][1][-1], expected_traffic_data / 1000000000
            )
            self.assertEqual(
                chart['summary']['download'], expected_traffic_data / 1000000000
            )
            _test_chart_properties(chart)

        with self.subTest('Test filtering for non-existing organization'):
            response = self.client.get(path, {'organization_slug': 'non-existing-org'})
            self.assertEqual(response.status_code, 404)

        self.client.force_login(operator)
        with self.subTest('Test non-org admin retrieve metric'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 403)

    def test_exporting_data_as_csv(self):
        def _test_csv_response(response):
            self.assertEqual(
                response.get('Content-Disposition'), 'attachment; filename=data.csv'
            )
            self.assertEqual(response.get('Content-Type'), 'text/csv')
            rows = response.content.decode('utf8').strip().split('\n')
            header = rows[0].strip().split(',')
            self.assertEqual(
                header,
                [
                    'time',
                    'wifi_clients - WiFi clients',
                    'download - General Traffic',
                    'upload - General Traffic',
                ],
            )
            last_line = rows[-1].strip().split(',')
            return last_line

        path = reverse('monitoring_general:api_dashboard_timeseries')
        org1 = self._create_org(name='org1', slug='org1')
        org2 = self._create_org(name='org2', slug='org2')
        org1_wifi_metric = self._create_org_wifi_client_metric(org1)
        org2_wifi_metric = self._create_org_wifi_client_metric(org2)
        org1_wan_metric = self._create_org_traffic_metric(org1, 'wan')
        org2_wan_metric = self._create_org_traffic_metric(org2, 'wan')

        org1_wifi_metric.write('00:23:4a:00:00:00')
        org2_wifi_metric.write('00:23:4b:00:00:00')
        org2_wifi_metric.write('00:14:5c:00:00:00')
        org1_wan_metric.write(1000000000)
        org2_wan_metric.write(2000000000)

        admin, org2_administrator, operator = self._create_test_users(org2)

        self.client.force_login(admin)
        with self.subTest('Test superuser exporting csv'):
            response = self.client.get(path, {'csv': '1'})
            last_line = _test_csv_response(response)
            self.assertEqual(
                last_line,
                [last_line[0], '3', '3.0', ''],
            )

        self.client.force_login(org2_administrator)
        with self.subTest('Test organization admin exporting csv'):
            response = self.client.get(path, {'csv': '1'})
            last_line = _test_csv_response(response)
            self.assertEqual(
                last_line,
                [last_line[0], '2', '2.0', ''],
            )

        self.client.force_login(operator)
        with self.subTest('Test non-organization admin exporting csv'):
            response = self.client.get(path, {'csv': 1})
            self.assertEqual(response.status_code, 403)

        self.client.logout()
        with self.subTest('Test unauthenticated user exporting csv'):
            response = self.client.get(path, {'csv': 1})
            self.assertEqual(response.status_code, 403)

    def test_filter_with_location_id(self):
        pass

    def test_group_by_time(self):
        admin = self._create_admin()
        self.client.force_login(admin)
        path = reverse('monitoring_general:api_dashboard_timeseries')
        with self.subTest('Test with valid group time'):
            response = self.client.get(path, {'time': '1d'})
            self.assertEqual(response.status_code, 200)
            self.assertIsInstance(response.data['charts'], list)

        with self.subTest('Test with invalid group time'):
            response = self.client.get(path, {'time': '3w'})
            self.assertEqual(response.status_code, 400)
