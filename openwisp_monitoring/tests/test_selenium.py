from time import sleep
from unittest.mock import patch

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import tag
from django.urls.base import reverse
from reversion.models import Version
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from swapper import load_model

from openwisp_controller.connection.tests.utils import CreateConnectionsMixin
from openwisp_monitoring.device.tests import (
    TestDeviceMonitoringMixin,
    TestWifiClientSessionMixin,
)
from openwisp_monitoring.monitoring.configuration import DEFAULT_DASHBOARD_TRAFFIC_CHART
from openwisp_monitoring.monitoring.migrations import create_general_metrics
from openwisp_utils.admin_theme.dashboard import DASHBOARD_TEMPLATES
from openwisp_utils.tests import SeleniumTestMixin as BaseSeleniumTestMixin

Device = load_model('config', 'Device')
DeviceConnection = load_model('connection', 'DeviceConnection')
DeviceData = load_model('device_monitoring', 'DeviceData')
AlertSettings = load_model('monitoring', 'AlertSettings')
Metric = load_model('monitoring', 'Metric')
Chart = load_model('monitoring', 'Chart')
Check = load_model('check', 'Check')


class SeleniumTestMixin(BaseSeleniumTestMixin):
    @classmethod
    def setUpClass(cls):
        """
        Sets up the necessary configurations for the test environment, ensuring
        that the dashboard templates render correctly during Selenium tests.

        During testing, the `OPENWISP_MONITORING_API_BASEURL` is set to
        `http://testserver`, a dummy value for the test environment. The dashboard
        templates are registered in the `AppConfig.ready` method, and these
        templates depend on specific URLs being correctly configured.

        Since mocking the `OPENWISP_MONITORING_API_BASEURL` does not update the
        URLs in the already registered dashboard templates, this method manually
        adjusts the template contexts to ensure they contain the correct URLs.
        """
        super().setUpClass()
        cls._dashboard_map_context = DASHBOARD_TEMPLATES[0][1].copy()
        cls._dashboard_timeseries_context = DASHBOARD_TEMPLATES[55][1].copy()
        DASHBOARD_TEMPLATES[0][1] = {
            'monitoring_device_list_url': reverse(
                'monitoring:api_location_device_list',
                args=['000'],
            ),
            'monitoring_location_geojson_url': reverse(
                'monitoring:api_location_geojson'
            ),
        }
        DASHBOARD_TEMPLATES[55][1]['api_url'] = reverse(
            'monitoring_general:api_dashboard_timeseries'
        )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        DASHBOARD_TEMPLATES[0][1] = cls._dashboard_map_context
        DASHBOARD_TEMPLATES[55][1] = cls._dashboard_timeseries_context

    def login(self, username=None, password=None, driver=None):
        super().login(username, password, driver)
        # Workaround for JS logic in chart-utils.js
        # which fails to perform a XHR request
        # during automated tests, it seems that the
        # lack of pause causes the request to fail randomly
        sleep(0.5)


@tag('selenium_tests')
class TestDeviceConnectionInlineAdmin(
    SeleniumTestMixin,
    TestDeviceMonitoringMixin,
    CreateConnectionsMixin,
    StaticLiveServerTestCase,
):
    config_app_label = 'config'

    def test_restoring_deleted_device(self):
        org = self._get_org()
        self._create_credentials(auto_add=True, organization=org)
        device = self._create_config(organization=org).device
        device_data = DeviceData.objects.get(id=device.id)
        device_checks = device_data.checks.all()
        for check in device_checks:
            check.perform_check()
        device_metric_ids = device_data.metrics.values_list('id', flat=True)
        device_chart_ids = Chart.objects.filter(
            metric_id__in=device_metric_ids
        ).values_list('id', flat=True)
        device_alert_setting_ids = AlertSettings.objects.filter(
            metric_id__in=device_metric_ids
        ).values_list('id', flat=True)
        self.assertEqual(len(device_alert_setting_ids), 3)
        self.assertEqual(len(device_metric_ids), 3)
        self.assertEqual(len(device_checks), 4)
        self.assertEqual(len(device_chart_ids), 3)

        self.login()

        # Save device to create revision.
        self.open(
            reverse(f'admin:{self.config_app_label}_device_change', args=[device.id])
        )
        self.hide_loading_overlay()
        self.wait_for(
            'element_to_be_clickable',
            By.XPATH,
            '//*[@id="device_form"]/div/div[1]/input[1]',
        ).click()
        try:
            WebDriverWait(self.web_driver, 5).until(
                EC.url_to_be(f'{self.live_server_url}/admin/config/device/')
            )
        except TimeoutException:
            self.fail('Failed saving device')
        # Delete the device
        device.deactivate()
        device.config.set_status_deactivated()
        self.open(
            reverse(f'admin:{self.config_app_label}_device_delete', args=[device.id])
        )
        self.find_element(
            By.CSS_SELECTOR, '#content form input[type="submit"]', timeout=5
        ).click()
        self.assertEqual(Device.objects.count(), 0)
        self.assertEqual(DeviceConnection.objects.count(), 0)
        self.assertEqual(Check.objects.count(), 0)
        self.assertEqual(Metric.objects.exclude(object_id=None).count(), 0)

        version_obj = Version.objects.get_deleted(model=Device).first()

        # Restore deleted device
        self.open(
            reverse(
                f'admin:{self.config_app_label}_device_recover', args=[version_obj.id]
            )
        )
        self.find_element(
            By.XPATH, '//*[@id="device_form"]/div/div[1]/input[1]'
        ).click()
        try:
            WebDriverWait(self.web_driver, 5).until(
                EC.url_to_be(f'{self.live_server_url}/admin/config/device/')
            )
        except TimeoutException:
            self.fail('Deleted device was not restored')

        self.assertEqual(Device.objects.count(), 1)
        self.assertEqual(DeviceConnection.objects.count(), 1)
        # Ensure that existing Metric, AlertSetting and Chart objects
        # was restored
        self.assertEqual(Metric.objects.filter(id__in=device_metric_ids).count(), 3)
        self.assertEqual(
            AlertSettings.objects.filter(id__in=device_alert_setting_ids).count(), 3
        )
        self.assertEqual(Chart.objects.filter(id__in=device_chart_ids).count(), 3)


@tag('selenium_tests')
class TestDashboardCharts(
    SeleniumTestMixin, TestDeviceMonitoringMixin, StaticLiveServerTestCase
):
    def setUp(self):
        super().setUp()
        # TransactionTestCase flushes the data, hence the metrics created
        # with migrations are lost. Only create general metrics if required.
        if Metric.objects.filter(object_id=None).count() != 2:
            create_general_metrics(None, None)
        self.assertEqual(Metric.objects.filter(object_id=None).count(), 2)

    @patch.dict(DEFAULT_DASHBOARD_TRAFFIC_CHART, {'__all__': ['wlan0', 'wlan1']})
    def test_dashboard_timeseries_charts(self):
        self.login()
        self.wait_for_visibility(
            By.CSS_SELECTOR, '#ow-chart-inner-container', timeout=5
        )
        self.wait_for_visibility(By.CSS_SELECTOR, '#ow-chart-utils', timeout=5)
        self.wait_for_visibility(By.CSS_SELECTOR, '#ow-chart-fallback', timeout=5)
        self.assertIn(
            'Insufficient data for selected time period.',
            self.find_element(By.CSS_SELECTOR, '#ow-chart-fallback').get_attribute(
                'innerHTML'
            ),
        )
        self.create_test_data()
        self.web_driver.refresh()
        self.wait_for_visibility(By.CSS_SELECTOR, '#ow-chart-contents', timeout=10)
        self.wait_for_visibility(By.CSS_SELECTOR, '#chart-0', timeout=10)
        self.wait_for_visibility(By.CSS_SELECTOR, '#chart-1', timeout=10)
        self.assertIn(
            'General WiFi Clients',
            self.find_element(By.CSS_SELECTOR, '#chart-0 > h3').get_attribute(
                'innerHTML'
            ),
        )
        self.assertIn(
            'General Traffic',
            self.find_element(By.CSS_SELECTOR, '#chart-1 > h3').get_attribute(
                'innerHTML'
            ),
        )
        self.assertIn(
            'Open WiFi session list',
            self.find_element(
                By.CSS_SELECTOR, '#chart-0-quick-link-container'
            ).get_attribute('innerHTML'),
        )


@tag('selenium_tests')
class TestWifiSessionInlineAdmin(
    SeleniumTestMixin,
    TestWifiClientSessionMixin,
    StaticLiveServerTestCase,
):
    config_app_label = 'config'

    def test_device_wifi_session_inline_change(self):
        dm = self._create_device_monitoring()
        device = dm.device
        self.login()
        path = f'admin:{self.config_app_label}_device_change'
        self.open(reverse(path, args=[device.pk]))
        self.hide_loading_overlay()
        # Make sure the wifi session inline doesn't exist
        self.wait_for_invisibility(By.CSS_SELECTOR, '#wifisession_set-group')
        # We are still on the device change page,
        # and now we will create new wifi sessions
        ws1 = self._create_wifi_session(device=device)
        wc2 = self._create_wifi_client(mac_address='22:33:44:55:66:88')
        ws2 = self._create_wifi_session(
            device=device, wifi_client=wc2, ssid='Test Wifi Session'
        )
        # Now press the 'Save' button on the device change page
        self.find_element(
            By.XPATH, '//*[@id="device_form"]/div/div[1]/input[3]'
        ).click()
        # Make sure the wifi session tab now
        # exists with the correct wifi sessions
        self.hide_loading_overlay()
        self.wait_for(
            'element_to_be_clickable', By.XPATH, '//*[@id="tabs-container"]/ul/li[7]/a'
        ).click()
        wifi_session_inline_form_error = (
            'ManagementForm data is missing '
            'or has been tampered with. Missing fields: '
            'wifisession_set-TOTAL_FORMS, wifisession_set-INITIAL_FORMS.'
        )
        # Make sure no inline formset errors
        # were encountered after saving
        self.assertNotIn(
            wifi_session_inline_form_error,
            self.find_element(By.CSS_SELECTOR, '#wifisession_set-group').get_attribute(
                'innerHTML'
            ),
        )
        # Make sure all wifi sessions are present
        self.assertIn(
            f'{ws1.ssid}',
            self.find_element(By.CSS_SELECTOR, '#wifisession_set-group').get_attribute(
                'innerHTML'
            ),
        )
        self.assertIn(
            f'{ws2.ssid}',
            self.find_element(By.CSS_SELECTOR, '#wifisession_set-group').get_attribute(
                'innerHTML'
            ),
        )
        self.assertIn(
            'View Full History of WiFi Sessions',
            self.find_element(By.CSS_SELECTOR, '#wifisession_set-group').get_attribute(
                'innerHTML'
            ),
        )
