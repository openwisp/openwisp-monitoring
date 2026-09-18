import os
import sys

# Add the project directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Run pytest directly on the file
import pytest

raise SystemExit(
    pytest.main(
        [
            "openwisp_monitoring/tests/test_selenium.py::TestDashboardMap::test_dashboard_map_popup_resizes_for_custom_status_labels"
        ]
    )
)
