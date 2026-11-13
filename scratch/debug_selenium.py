import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

from unittest.mock import patch

from django.test import override_settings
from selenium.webdriver.common.by import By

from openwisp_monitoring.tests.test_selenium import TestDashboardMap
from openwisp_utils.admin_theme.dashboard import DASHBOARD_TEMPLATES


class DebugTest(TestDashboardMap):
    def test_debug_scenario(self):
        org = self._get_org()
        location = self._create_location(
            type="outdoor", name="Test-Location", organization=org
        )
        device = self._create_device(
            name="Test-Device", mac_address="00:00:00:00:00:01", organization=org
        )
        self._create_object_location(
            content_object=device,
            location=location,
            organization=org,
        )

        test_cases = [
            (
                "fits",
                {
                    "ok": "Operational Devices",
                    "problem": "Devices With Problems",
                    "critical": "Critically Unhealthy",
                    "unknown": "Unknown Status",
                    "deactivated": "Deactivated",
                },
                True,
            ),
            (
                "exceeds",
                {
                    "ok": "Very Long Text " * 15,
                    "problem": "Very Long Text " * 15,
                    "critical": "Very Long Text " * 15,
                    "unknown": "Very Long Text " * 15,
                    "deactivated": "Very Long Text " * 15,
                },
                False,
            ),
        ]

        self.login()
        for case_name, custom_labels, expected_one_row in test_cases:
            with self.subTest(case_name=case_name):
                with patch.dict(
                    DASHBOARD_TEMPLATES[0][1]["monitoring_labels"], custom_labels
                ):
                    self.web_driver.get(self.live_server_url + "/admin/")
                    self.wait_for_visibility(By.CSS_SELECTOR, ".leaflet-container")
                    self._open_popup("_owGeoMap", location.id)
                    self.wait_for_visibility(By.CSS_SELECTOR, ".map-detail")

                    self._wait_for_popup_table_ready()

                    map_width = self.web_driver.execute_script(
                        "return django.jQuery('#device-map-container').width();"
                    )
                    popup_width = self.web_driver.execute_script(
                        "return django.jQuery('.map-detail').width();"
                    )
                    popup_content_width = self.web_driver.execute_script(
                        "return django.jQuery('.leaflet-popup-content').width();"
                    )

                    print(
                        f"\n{case_name}: map={map_width}, popup={popup_width}, content={popup_content_width}"
                    )

                    self.assertGreaterEqual(popup_width, 410)
                    self.assertLessEqual(popup_width, map_width * 0.6)
                    self.assertLessEqual(popup_width, popup_content_width)

                    is_one_row = self.web_driver.execute_script("""
                        const buttons = [...document.querySelectorAll(".map-detail .status-filter")];
                        return buttons.length > 0 && buttons.every(
                            (button) => button.getBoundingClientRect().top === buttons[0].getBoundingClientRect().top
                        );
                        """)
                    self.assertEqual(is_one_row, expected_one_row)
