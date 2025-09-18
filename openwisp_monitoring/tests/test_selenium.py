from time import sleep
from unittest.mock import patch
from urllib.parse import quote_plus

from django.contrib.auth.models import Permission
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
from openwisp_controller.geo.tests.utils import TestGeoMixin
from openwisp_monitoring.device.tests import (
    TestDeviceMonitoringMixin,
    TestWifiClientSessionMixin,
)
from openwisp_monitoring.monitoring.configuration import DEFAULT_DASHBOARD_TRAFFIC_CHART
from openwisp_monitoring.monitoring.migrations import create_general_metrics
from openwisp_utils.admin_theme.dashboard import DASHBOARD_TEMPLATES
from openwisp_utils.tests import SeleniumTestMixin as BaseSeleniumTestMixin

from ..device import settings as device_app_settings

Device = load_model("config", "Device")
DeviceConnection = load_model("connection", "DeviceConnection")
DeviceData = load_model("device_monitoring", "DeviceData")
AlertSettings = load_model("monitoring", "AlertSettings")
Metric = load_model("monitoring", "Metric")
Chart = load_model("monitoring", "Chart")
Check = load_model("check", "Check")
Location = load_model("geo", "Location")
DeviceLocation = load_model("geo", "DeviceLocation")
Floorplan = load_model("geo", "Floorplan")


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
            "monitoring_device_list_url": reverse(
                "monitoring:api_location_device_list",
                args=["000"],
            ),
            "monitoring_location_geojson_url": reverse(
                "monitoring:api_location_geojson"
            ),
            "monitoring_indoor_coordinates_list": reverse(
                "monitoring:api_indoor_coordinates_list", args=["000"]
            ),
            "monitoring_labels": {
                "ok": device_app_settings.HEALTH_STATUS_LABELS["ok"],
                "problem": device_app_settings.HEALTH_STATUS_LABELS["problem"],
                "critical": device_app_settings.HEALTH_STATUS_LABELS["critical"],
                "unknown": device_app_settings.HEALTH_STATUS_LABELS["unknown"],
                "deactivated": device_app_settings.HEALTH_STATUS_LABELS["deactivated"],
            },
        }
        DASHBOARD_TEMPLATES[55][1]["api_url"] = reverse(
            "monitoring_general:api_dashboard_timeseries"
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


@tag("selenium_tests")
class TestDeviceConnectionInlineAdmin(
    SeleniumTestMixin,
    TestDeviceMonitoringMixin,
    CreateConnectionsMixin,
    StaticLiveServerTestCase,
):
    config_app_label = "config"

    def test_restoring_deleted_device(self):
        org = self._get_org()
        self._create_credentials(auto_add=True, organization=org)
        device = self._create_config(organization=org).device
        device_data = DeviceData.objects.get(id=device.id)
        device_checks = device_data.checks.all()
        for check in device_checks:
            check.perform_check()
        device_metric_ids = device_data.metrics.values_list("id", flat=True)
        device_chart_ids = Chart.objects.filter(
            metric_id__in=device_metric_ids
        ).values_list("id", flat=True)
        device_alert_setting_ids = AlertSettings.objects.filter(
            metric_id__in=device_metric_ids
        ).values_list("id", flat=True)
        self.assertEqual(len(device_alert_setting_ids), 3)
        self.assertEqual(len(device_metric_ids), 3)
        self.assertEqual(len(device_checks), 4)
        self.assertEqual(len(device_chart_ids), 3)

        self.login()

        # Save device to create revision.
        self.open(
            reverse(f"admin:{self.config_app_label}_device_change", args=[device.id])
        )
        self.hide_loading_overlay()
        self.wait_for(
            "element_to_be_clickable",
            By.XPATH,
            '//*[@id="device_form"]/div/div[1]/input[1]',
        ).click()
        try:
            WebDriverWait(self.web_driver, 5).until(
                EC.url_to_be(f"{self.live_server_url}/admin/config/device/")
            )
        except TimeoutException:
            self.fail("Failed saving device")
        # Delete the device
        device.deactivate()
        device.config.set_status_deactivated()
        self.open(
            reverse(f"admin:{self.config_app_label}_device_delete", args=[device.id])
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
                f"admin:{self.config_app_label}_device_recover", args=[version_obj.id]
            )
        )
        self.find_element(
            By.XPATH, '//*[@id="device_form"]/div/div[1]/input[1]'
        ).click()
        try:
            WebDriverWait(self.web_driver, 5).until(
                EC.url_to_be(f"{self.live_server_url}/admin/config/device/")
            )
        except TimeoutException:
            self.fail("Deleted device was not restored")

        self.assertEqual(Device.objects.count(), 1)
        self.assertEqual(DeviceConnection.objects.count(), 1)
        # Ensure that existing Metric, AlertSetting and Chart objects
        # was restored
        self.assertEqual(Metric.objects.filter(id__in=device_metric_ids).count(), 3)
        self.assertEqual(
            AlertSettings.objects.filter(id__in=device_alert_setting_ids).count(), 3
        )
        self.assertEqual(Chart.objects.filter(id__in=device_chart_ids).count(), 3)


@tag("selenium_tests")
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

    @patch.dict(DEFAULT_DASHBOARD_TRAFFIC_CHART, {"__all__": ["wlan0", "wlan1"]})
    def test_dashboard_timeseries_charts(self):
        self.login()
        self.wait_for_visibility(
            By.CSS_SELECTOR, "#ow-chart-inner-container", timeout=5
        )
        self.wait_for_visibility(By.CSS_SELECTOR, "#ow-chart-utils", timeout=5)
        self.wait_for_visibility(By.CSS_SELECTOR, "#ow-chart-fallback", timeout=5)
        self.assertIn(
            "Insufficient data for selected time period.",
            self.find_element(By.CSS_SELECTOR, "#ow-chart-fallback").get_attribute(
                "innerHTML"
            ),
        )
        self.create_test_data()
        self.web_driver.refresh()
        self.wait_for_visibility(By.CSS_SELECTOR, "#ow-chart-contents", timeout=10)
        self.wait_for_visibility(By.CSS_SELECTOR, "#chart-0", timeout=10)
        self.wait_for_visibility(By.CSS_SELECTOR, "#chart-1", timeout=10)
        self.assertIn(
            "General WiFi Clients",
            self.find_element(By.CSS_SELECTOR, "#chart-0 > h3").get_attribute(
                "innerHTML"
            ),
        )
        self.assertIn(
            "General Traffic",
            self.find_element(By.CSS_SELECTOR, "#chart-1 > h3").get_attribute(
                "innerHTML"
            ),
        )
        self.assertIn(
            "Open WiFi session list",
            self.find_element(
                By.CSS_SELECTOR, "#chart-0-quick-link-container"
            ).get_attribute("innerHTML"),
        )


@tag("selenium_tests")
class TestWifiSessionInlineAdmin(
    SeleniumTestMixin,
    TestWifiClientSessionMixin,
    StaticLiveServerTestCase,
):
    config_app_label = "config"

    def test_device_wifi_session_inline_change(self):
        dm = self._create_device_monitoring()
        device = dm.device
        self.login()
        path = f"admin:{self.config_app_label}_device_change"
        self.open(reverse(path, args=[device.pk]))
        self.hide_loading_overlay()
        # Make sure the wifi session inline doesn't exist
        self.wait_for_invisibility(By.CSS_SELECTOR, "#wifisession_set-group")
        # We are still on the device change page,
        # and now we will create new wifi sessions
        ws1 = self._create_wifi_session(device=device)
        wc2 = self._create_wifi_client(mac_address="22:33:44:55:66:88")
        ws2 = self._create_wifi_session(
            device=device, wifi_client=wc2, ssid="Test Wifi Session"
        )
        # Now press the 'Save' button on the device change page
        self.find_element(
            By.XPATH, '//*[@id="device_form"]/div/div[1]/input[3]'
        ).click()
        # Make sure the wifi session tab now
        # exists with the correct wifi sessions
        self.hide_loading_overlay()
        self.wait_for(
            "element_to_be_clickable", By.XPATH, '//*[@id="tabs-container"]/ul/li[7]/a'
        ).click()
        wifi_session_inline_form_error = (
            "ManagementForm data is missing "
            "or has been tampered with. Missing fields: "
            "wifisession_set-TOTAL_FORMS, wifisession_set-INITIAL_FORMS."
        )
        # Make sure no inline formset errors
        # were encountered after saving
        self.assertNotIn(
            wifi_session_inline_form_error,
            self.find_element(By.CSS_SELECTOR, "#wifisession_set-group").get_attribute(
                "innerHTML"
            ),
        )
        # Make sure all wifi sessions are present
        self.assertIn(
            f"{ws1.ssid}",
            self.find_element(By.CSS_SELECTOR, "#wifisession_set-group").get_attribute(
                "innerHTML"
            ),
        )
        self.assertIn(
            f"{ws2.ssid}",
            self.find_element(By.CSS_SELECTOR, "#wifisession_set-group").get_attribute(
                "innerHTML"
            ),
        )
        self.assertIn(
            "View Full History of WiFi Sessions",
            self.find_element(By.CSS_SELECTOR, "#wifisession_set-group").get_attribute(
                "innerHTML"
            ),
        )


@tag("selenium_tests")
class TestDashboardMap(
    SeleniumTestMixin, TestDeviceMonitoringMixin, TestGeoMixin, StaticLiveServerTestCase
):
    object_model = Device
    location_model = Location
    floorplan_model = Floorplan
    object_location_model = DeviceLocation

    def open_popup(self, mapType, id):
        self.web_driver.execute_script(
            "return window[arguments[0]].utils.openPopup(arguments[1]);",
            mapType,
            str(id),
        )

    def test_features_on_device_popup(self):
        d1 = self._create_device(name="Test-Device1", mac_address="00:00:00:00:00:01")
        d2 = self._create_device(name="Test-Device2", mac_address="00:00:00:00:00:02")
        d2.monitoring.status = "ok"
        d2.monitoring.save()
        location = self._create_location(type="outdoor", name="Test-Location")
        self._create_object_location(
            content_object=d1,
            location=location,
        )
        self._create_object_location(
            content_object=d2,
            location=location,
        )
        self.login()
        self.wait_for_visibility(By.CSS_SELECTOR, ".leaflet-container")
        self.open_popup("_owGeoMap", location.id)
        self.wait_for_visibility(By.CSS_SELECTOR, ".map-detail", timeout=5)
        table_entries = self.find_elements(By.CSS_SELECTOR, ".map-detail tbody tr")
        self.assertEqual(len(table_entries), 2)

        with self.subTest("Test filtering by status for status ok"):
            status_ok = self.find_element(By.CSS_SELECTOR, ".map-detail .health-ok")
            status_ok_close_btn = self.find_element(
                By.CSS_SELECTOR, ".health-ok .remove-icon", wait_for="presence"
            )
            self.assertFalse(status_ok_close_btn.is_displayed())
            status_ok.click()
            self.assertTrue(status_ok_close_btn.is_displayed())
            self.wait_for_invisibility(
                By.CSS_SELECTOR, ".map-detail .ow-loading-spinner"
            )
            sleep(0.5)
            table_entries = self.find_elements(By.CSS_SELECTOR, ".map-detail tbody tr")
            self.assertEqual(len(table_entries), 1)
            self.assertIn(d2.name, table_entries[0].text)

        with self.subTest("Test filtering by status for status ok and unknown"):
            status_unknown = self.find_element(
                By.CSS_SELECTOR, ".map-detail .health-unknown"
            )
            status_unknown_close_btn = self.find_element(
                By.CSS_SELECTOR, ".health-unknown .remove-icon", wait_for="presence"
            )
            self.assertFalse(status_unknown_close_btn.is_displayed())
            status_unknown.click()
            self.assertTrue(status_unknown_close_btn.is_displayed())
            self.wait_for_invisibility(
                By.CSS_SELECTOR, ".map-detail .ow-loading-spinner"
            )
            sleep(0.5)
            table_entries = self.find_elements(By.CSS_SELECTOR, ".map-detail tbody tr")
            self.assertEqual(len(table_entries), 2)

        with self.subTest("Test removing filters by clicking close button"):
            status_ok_close_btn.click()
            self.assertFalse(status_ok_close_btn.is_displayed())
            self.wait_for_invisibility(
                By.CSS_SELECTOR, ".map-detail .ow-loading-spinner"
            )
            sleep(0.5)
            table_entries = self.find_elements(By.CSS_SELECTOR, ".map-detail tbody tr")
            self.assertEqual(len(table_entries), 1)
            self.assertIn(d1.name, table_entries[0].text)
            status_unknown.click()
            self.assertFalse(status_unknown_close_btn.is_displayed())
            self.wait_for_invisibility(
                By.CSS_SELECTOR, ".map-detail .ow-loading-spinner"
            )
            sleep(0.5)
            table_entries = self.find_elements(By.CSS_SELECTOR, ".map-detail tbody tr")
            self.assertEqual(len(table_entries), 2)

        with self.subTest("Test search field"):
            input_field = self.find_element(By.CSS_SELECTOR, "#device-search")
            input_field.send_keys("device1")
            self.wait_for_invisibility(
                By.CSS_SELECTOR, ".map-detail .ow-loading-spinner"
            )
            sleep(0.5)
            table_entries = self.find_elements(By.CSS_SELECTOR, ".map-detail tbody tr")
            self.assertEqual(len(table_entries), 1)
            self.assertIn(d1.name, table_entries[0].text)

        with self.subTest("Test clearing input field"):
            input_field.clear()
            # Just clearing the input field does not trigger the event listeners
            input_field.send_keys(" ")
            self.wait_for_invisibility(
                By.CSS_SELECTOR, ".map-detail .ow-loading-spinner"
            )
            sleep(0.5)
            table_entries = self.find_elements(By.CSS_SELECTOR, ".map-detail tbody tr")
            self.assertEqual(len(table_entries), 2)

        with self.subTest("Test filtering to get no results"):
            input_field.send_keys("Non-Existent-Device")
            self.wait_for_invisibility(
                By.CSS_SELECTOR, ".map-detail .ow-loading-spinner"
            )
            sleep(0.5)
            table_entries = self.find_elements(By.CSS_SELECTOR, ".map-detail tbody tr")
            self.assertEqual(len(table_entries), 1)
            self.assertIn("No devices found", table_entries[0].text)

        with self.subTest("Verify show floor button is not present"):
            self.wait_for_invisibility(By.CSS_SELECTOR, ".map-detail .floorplan-btn")

    def test_infinite_scroll_on_popup(self):
        location = self._create_location(type="indoor", name="Test-Location")
        for i in range(20):
            device = self._create_device(
                name=f"Test-Device-{i + 1}",
                mac_address=f"00:00:00:00:00:{i + 1:02d}",
                organization=location.organization,
            )
            self._create_object_location(
                content_object=device,
                location=location,
            )
        self.login()
        self.wait_for_visibility(By.CSS_SELECTOR, ".leaflet-container")
        self.open_popup("_owGeoMap", location.id)
        self.wait_for_visibility(By.CSS_SELECTOR, ".map-detail", timeout=5)
        table_container = self.find_element(
            By.CSS_SELECTOR, ".map-detail .table-container"
        )
        table_entries = self.find_elements(By.CSS_SELECTOR, ".map-detail tbody tr")
        self.assertEqual(len(table_entries), 10)
        self.web_driver.execute_script(
            "arguments[0].scrollTop = arguments[0].scrollHeight", table_container
        )
        self.wait_for_invisibility(By.CSS_SELECTOR, ".map-detail .ow-loading-spinner")
        sleep(0.5)
        table_entries = self.find_elements(By.CSS_SELECTOR, ".map-detail tbody tr")
        self.assertEqual(len(table_entries), 20)

    def test_url_fragment_actions_on_geo_map(self):
        device_location = self._create_object_location()
        device = device_location.device
        location = device_location.location
        self.login()
        mapId = "dashboard-geo-map"

        with self.subTest("Test setting url fragments on click event of node"):
            self.open_popup("_owGeoMap", location.id)
            current_hash = self.web_driver.execute_script(
                "return window.location.hash;"
            )
            expected_hash = f"id={mapId}&nodeId={location.id}"
            self.assertIn(expected_hash, current_hash)

        with self.subTest("Test applying url fragment state on map"):
            current_url = self.web_driver.current_url
            self.web_driver.switch_to.new_window("tab")
            tabs = self.web_driver.window_handles
            self.web_driver.switch_to.window(tabs[1])
            self.web_driver.get(current_url)
            sleep(0.5)
            popup = self.find_element(By.CSS_SELECTOR, ".map-detail")
            device_link = self.find_element(
                By.XPATH, f".//td[@class='col-name']/a[text()='{device.name}']"
            )
            self.assertTrue(popup.is_displayed())
            self.assertTrue(device_link.is_displayed())
            self.web_driver.close()
            self.web_driver.switch_to.window(tabs[0])

        with self.subTest("Test with incorrect node Id"):
            incorrect_url = (
                f"{self.live_server_url}/admin/#id={mapId}&nodeId=incorrectId"
            )
            self.web_driver.switch_to.new_window("tab")
            tabs = self.web_driver.window_handles
            self.web_driver.switch_to.window(tabs[1])
            self.web_driver.get(incorrect_url)
            sleep(0.5)
            self.wait_for_invisibility(By.CSS_SELECTOR, ".map-detail")
            self.web_driver.close()
            self.web_driver.switch_to.window(tabs[0])

    def test_floorplan_overlay(self):
        org = self._get_org()
        location = self._create_location(type="indoor", organization=org)
        floor1 = self._create_floorplan(floor=1, location=location)
        floor2 = self._create_floorplan(floor=2, location=location)
        device1 = self._create_device(
            name="Test-Device1", mac_address="00:00:00:00:00:01", organization=org
        )
        device2 = self._create_device(
            name="Test-Device2", mac_address="00:00:00:00:00:02", organization=org
        )
        self._create_object_location(
            content_object=device1,
            location=location,
            floorplan=floor1,
            organization=org,
        )
        self._create_object_location(
            content_object=device2,
            location=location,
            floorplan=floor2,
            organization=org,
        )
        self.login()
        self.wait_for_visibility(By.CSS_SELECTOR, "#device-map-container")
        self.wait_for_visibility(By.CSS_SELECTOR, ".leaflet-container")
        self.open_popup("_owGeoMap", location.id)

        with self.subTest("Test floorplan rendering"):
            self.wait_for(
                "element_to_be_clickable",
                By.CSS_SELECTOR,
                ".map-detail .floorplan-btn",
                timeout=5,
            ).click()
            canvases = self.find_elements(
                By.CSS_SELECTOR, "#floor-content-1 canvas", timeout=5
            )
            self.assertIsNotNone(canvases)

        with self.subTest("Test floorplan navigation"):
            right_arrow = self.find_element(
                By.CSS_SELECTOR, "#floorplan-navigation .right-arrow"
            )
            right_arrow.click()
            sleep(0.3)
            floor_heading = self.find_element(By.CSS_SELECTOR, "#floorplan-title")
            self.assertIn("2nd floor", floor_heading.text.lower())
            canvases = self.find_elements(
                By.CSS_SELECTOR, "#floor-content-2 canvas", timeout=5
            )
            self.assertIsNotNone(canvases)

            left_arrow = self.find_element(
                By.CSS_SELECTOR, "#floorplan-navigation .left-arrow"
            )
            left_arrow.click()
            sleep(0.3)
            floor_heading = self.find_element(By.CSS_SELECTOR, "#floorplan-title")
            self.assertIn("1st floor", floor_heading.text.lower())
            canvases = self.find_elements(
                By.CSS_SELECTOR, "#floor-content-1 canvas", timeout=5
            )
            self.assertIsNotNone(canvases)

            second_floor_btn = self.find_element(
                By.CSS_SELECTOR, "#floorplan-navigation .floor-btn[data-floor='2']"
            )
            second_floor_btn.click()
            floor_heading = self.find_element(By.CSS_SELECTOR, "#floorplan-title")
            self.assertIn("2nd floor", floor_heading.text.lower())
            canvases = self.find_elements(
                By.CSS_SELECTOR, "#floor-content-2 canvas", timeout=5
            )
            self.assertIsNotNone(canvases)

        with self.subTest("Test redirecting to device page from indoor map"):
            self.open_popup("_owIndoorMap", device2.id)
            open_device_btn = self.find_element(
                By.CSS_SELECTOR,
                ".open-device-btn-container .open-device-btn",
                timeout=5,
            )
            open_device_btn.click()
            try:
                WebDriverWait(self.web_driver, 5).until(
                    EC.url_to_be(
                        f"{self.live_server_url}/admin/config/device/{device2.id}/change/"
                    )
                )
            except TimeoutException:
                self.fail("Failed to redirect to device change page")
            self.assertIn(
                f"/config/device/{device2.id}/change/", self.web_driver.current_url
            )

    def test_switching_floorplan_in_fullscreen_mode(self):
        org = self._get_org()
        location = self._create_location(type="indoor", organization=org)
        floor1 = self._create_floorplan(floor=1, location=location)
        floor2 = self._create_floorplan(floor=2, location=location)
        device1 = self._create_device(
            name="Test-Device1", mac_address="00:00:00:00:00:01", organization=org
        )
        device2 = self._create_device(
            name="Test-Device2", mac_address="00:00:00:00:00:02", organization=org
        )
        self._create_object_location(
            content_object=device1,
            location=location,
            floorplan=floor1,
            organization=org,
        )
        self._create_object_location(
            content_object=device2,
            location=location,
            floorplan=floor2,
            organization=org,
        )
        self.login()
        self.wait_for_visibility(By.CSS_SELECTOR, "#device-map-container")
        self.wait_for_visibility(By.CSS_SELECTOR, ".leaflet-container")
        self.open_popup("_owGeoMap", location.id)
        self.wait_for(
            "element_to_be_clickable", By.CSS_SELECTOR, ".map-detail .floorplan-btn"
        ).click()
        canvases = self.find_elements(
            By.CSS_SELECTOR, "#floor-content-1 canvas", timeout=5
        )
        self.assertIsNotNone(canvases)
        fullscreen_btn = self.find_element(
            By.CSS_SELECTOR, "#floor-content-1 .leaflet-control-fullscreen-button"
        )
        fullscreen_btn.click()
        sleep(0.5)
        container = self.find_element(
            By.CSS_SELECTOR, "#floor-content-1 .leaflet-container"
        )
        self.assertIn("leaflet-fullscreen-on", container.get_attribute("class"))
        right_arrow = self.find_element(
            By.CSS_SELECTOR, "#floorplan-navigation .right-arrow"
        )
        right_arrow.click()
        sleep(0.5)
        container = self.find_element(
            By.CSS_SELECTOR, "#floor-content-1 .leaflet-container", wait_for="presence"
        )
        self.assertNotIn("leaflet-fullscreen-on", container.get_attribute("class"))
        floor_heading = self.find_element(By.CSS_SELECTOR, "#floorplan-title")
        self.assertIn("2nd floor", floor_heading.text.lower())
        canvases = self.find_elements(
            By.CSS_SELECTOR, "#floor-content-2 canvas", timeout=5
        )
        self.assertIsNotNone(canvases)

    def test_url_fragment_actions_on_indoor_map(self):
        org = self._get_org()
        device = self._create_device(organization=org)
        location = self._create_location(type="indoor", organization=org)
        floorplan = self._create_floorplan(floor=1, location=location)
        device_location = self._create_object_location(
            content_object=device,
            location=location,
            floorplan=floorplan,
            organization=org,
        )
        self.login()
        self.open_popup("_owGeoMap", location.id)
        self.wait_for(
            "element_to_be_clickable",
            By.CSS_SELECTOR,
            ".map-detail .floorplan-btn",
            timeout=5,
        ).click()
        sleep(0.5)
        mapId = "dashboard-geo-map"
        indoorMapId = f"{location.id}:{floorplan.floor}"

        with self.subTest("Test setting url fragments on click event of node"):
            self.open_popup("_owIndoorMap", device.id)
            # import ipdb; ipdb.set_trace()
            current_hash = self.web_driver.execute_script(
                "return window.location.hash;"
            )
            expected_hash = (
                f"#id={mapId}&nodeId={location.id};"
                f"id={quote_plus(indoorMapId)}&nodeId={device_location.id}"
            )
            self.assertIn(expected_hash, current_hash)

        with self.subTest("Test applying url fragment state on indoor map"):
            current_url = self.web_driver.current_url
            self.web_driver.switch_to.new_window("tab")
            tabs = self.web_driver.window_handles
            self.web_driver.switch_to.window(tabs[1])
            self.web_driver.get(current_url)
            sleep(0.5)
            popup = self.find_element(By.CSS_SELECTOR, ".njg-tooltip-inner")
            self.assertTrue(popup.is_displayed())
            self.assertIn(device.name, popup.get_attribute("innerHTML"))
            self.web_driver.close()
            self.web_driver.switch_to.window(tabs[0])

        with self.subTest("Test with incorrect node Id"):
            incorrect_url = (
                f"{self.live_server_url}/admin/#id={indoorMapId}&nodeId=incorrectId"
            )
            self.web_driver.switch_to.new_window("tab")
            tabs = self.web_driver.window_handles
            self.web_driver.switch_to.window(tabs[1])
            self.web_driver.get(incorrect_url)
            sleep(0.5)
            self.wait_for_invisibility(By.CSS_SELECTOR, ".njg-tooltip-inner")
            self.web_driver.close()
            self.web_driver.switch_to.window(tabs[0])

    def test_dashboard_map_without_permissions(self):
        user = self._create_user(
            username="testuser", password="password", is_staff=True, is_superuser=True
        )
        permissions = Permission.objects.filter(codename__endswith="devicelocation")
        user.user_permissions.remove(*permissions)
        self.login(username="testuser", password="password")
        no_data_div = self.find_element(By.CSS_SELECTOR, ".no-data")
        self.assertTrue(no_data_div.is_displayed())
        self.assertIn("No map data to show.", no_data_div.text)
