"""Check the focused CI entry point rejects unsupported arguments."""

import os
import runpy
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent


class TestCiEntrypoint(unittest.TestCase):
    def test_rejects_unsupported_arguments(self):
        for arguments in (
            ("--settings=other",),
            ("--testrunner=other.Runner",),
            ("--noinput",),
            ("os.system",),
            ("openwisp_monitoring.tests.test_missing",),
        ):
            with self.subTest(arguments=arguments):
                result = subprocess.run(
                    ["./runtests", *arguments],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("Unsupported test argument", result.stderr)

    def test_focused_labels_select_their_configuration(self):
        runner = runpy.run_path(str(ROOT / "runtests.py"))["run_focused_tests"]
        for label, sample in (
            ("openwisp_monitoring.check.tests.test_models", ""),
            (
                "openwisp_monitoring.db.backends.influxdb.tests.TestDatabaseClient.test_forbidden_queries",
                "",
            ),
            ("openwisp2.sample_monitoring.tests", "1"),
        ):
            with self.subTest(label=label), patch.dict(
                os.environ, {"SAMPLE_APP": ""}
            ), patch.object(sys, "argv", ["runtests.py"]), patch(
                "django.setup"
            ), patch.dict(
                runner.__globals__, {"validate_test_labels": lambda labels: None}
            ):
                runner([label, "--noinput"])
                self.assertEqual(os.environ["SAMPLE_APP"], sample)
                self.assertEqual(sys.argv[1:], ["test", label, "--noinput"])


if __name__ == "__main__":
    unittest.main()
