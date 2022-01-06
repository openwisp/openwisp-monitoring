from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls.base import reverse
from reversion.models import Version
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, UnexpectedAlertPresentException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from swapper import load_model

from openwisp_controller.connection.tests.utils import CreateConnectionsMixin
from openwisp_controller.tests.utils import SeleniumTestMixin
from openwisp_monitoring.device.tests import TestDeviceMonitoringMixin

Device = load_model('config', 'Device')
DeviceConnection = load_model('connection', 'DeviceConnection')
DeviceData = load_model('device_monitoring', 'DeviceData')
AlertSettings = load_model('monitoring', 'AlertSettings')
Metric = load_model('monitoring', 'Metric')
Chart = load_model('monitoring', 'Chart')
Check = load_model('check', 'Check')


class TestDeviceConnectionInlineAdmin(
    SeleniumTestMixin,
    TestDeviceMonitoringMixin,
    CreateConnectionsMixin,
    StaticLiveServerTestCase,
):
    config_app_label = 'config'
    admin_username = 'admin'
    admin_password = 'password'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        chrome_options = webdriver.ChromeOptions()
        if getattr(settings, 'SELENIUM_HEADLESS', True):
            chrome_options.add_argument('--headless')
        chrome_options.add_argument('--window-size=1366,768')
        chrome_options.add_argument('--ignore-certificate-errors')
        chrome_options.add_argument('--remote-debugging-port=9222')
        capabilities = DesiredCapabilities.CHROME
        capabilities['goog:loggingPrefs'] = {'browser': 'ALL'}
        cls.web_driver = webdriver.Chrome(
            options=chrome_options, desired_capabilities=capabilities
        )

    @classmethod
    def tearDownClass(cls):
        cls.web_driver.quit()
        super().tearDownClass()

    def setUp(self):
        self.admin = self._create_admin(
            username=self.admin_username, password=self.admin_password
        )
        super().setUp()

    def tearDown(self):
        # Accept unsaved changes alert to allow other tests to run
        try:
            self.web_driver.refresh()
        except UnexpectedAlertPresentException:
            self.web_driver.switch_to_alert().accept()
        else:
            try:
                WebDriverWait(self.web_driver, 1).until(EC.alert_is_present())
            except TimeoutException:
                pass
            else:
                self.web_driver.switch_to_alert().accept()
        self.web_driver.refresh()
        WebDriverWait(self.web_driver, 2).until(
            EC.visibility_of_element_located((By.XPATH, '//*[@id="site-name"]'))
        )
        super().tearDown()

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
        self.assertEqual(len(device_alert_setting_ids), 2)
        self.assertEqual(len(device_metric_ids), 2)
        self.assertEqual(len(device_checks), 2)
        self.assertEqual(len(device_chart_ids), 3)

        self.login()

        # Save device to create revision.
        self.open(
            reverse(f'admin:{self.config_app_label}_device_change', args=[device.id])
        )
        self.web_driver.find_element_by_xpath(
            '//*[@id="device_form"]/div/div[1]/input[1]'
        ).click()
        try:
            WebDriverWait(self.web_driver, 5).until(
                EC.url_to_be(f'{self.live_server_url}/admin/config/device/')
            )
        except TimeoutException:
            self.fail('Failed saving device')

        # Delete the device
        self.open(
            reverse(f'admin:{self.config_app_label}_device_delete', args=[device.id])
        )
        self.web_driver.find_element_by_xpath(
            '//*[@id="content"]/form/div/input[2]'
        ).click()
        self.assertEqual(Device.objects.count(), 0)
        self.assertEqual(DeviceConnection.objects.count(), 0)
        self.assertEqual(Check.objects.count(), 0)
        self.assertEqual(Metric.objects.count(), 0)

        version_obj = Version.objects.get_deleted(model=Device).first()

        # Restore deleted device
        self.open(
            reverse(
                f'admin:{self.config_app_label}_device_recover', args=[version_obj.id]
            )
        )
        self.web_driver.find_element_by_xpath(
            '//*[@id="device_form"]/div/div[1]/input[1]'
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
        self.assertEqual(Metric.objects.filter(id__in=device_metric_ids).count(), 2)
        self.assertEqual(
            AlertSettings.objects.filter(id__in=device_alert_setting_ids).count(), 2
        )
        self.assertEqual(Chart.objects.filter(id__in=device_chart_ids).count(), 3)
