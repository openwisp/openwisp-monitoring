"""Check the focused CI entry point rejects unsupported arguments."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

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
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copy2(ROOT / "runtests", root / "runtests")
            shutil.copy2(ROOT / "runtests.py", root / "runtests.py")
            (root / "django" / "core").mkdir(parents=True)
            (root / "openwisp_monitoring" / "tests").mkdir(parents=True)
            (root / "openwisp_monitoring" / "db" / "backends" / "influxdb").mkdir(
                parents=True
            )
            (root / "tests" / "openwisp2" / "sample_monitoring").mkdir(parents=True)
            for package in (
                root / "django",
                root / "django" / "core",
                root / "openwisp_monitoring",
                root / "openwisp_monitoring" / "tests",
                root / "openwisp_monitoring" / "db",
                root / "openwisp_monitoring" / "db" / "backends",
                root / "openwisp_monitoring" / "db" / "backends" / "influxdb",
                root / "tests" / "openwisp2",
                root / "tests" / "openwisp2" / "sample_monitoring",
            ):
                (package / "__init__.py").touch()
            (root / "django" / "__init__.py").write_text("def setup(): pass\n")
            (root / "django" / "core" / "management.py").write_text(
                "import json, os\n"
                "def execute_from_command_line(args):\n"
                '    print(json.dumps({"sample": os.environ.get("SAMPLE_APP"), '
                '"args": args[1:]}))\n'
            )
            for module in (
                root / "openwisp_monitoring" / "tests" / "test_probe.py",
                root
                / "openwisp_monitoring"
                / "db"
                / "backends"
                / "influxdb"
                / "tests.py",
                root / "tests" / "openwisp2" / "sample_monitoring" / "tests.py",
            ):
                module.write_text(
                    "import unittest\n"
                    "class TestProbe(unittest.TestCase):\n"
                    "    def test_ok(self): pass\n"
                )
            for label, sample in (
                ("openwisp_monitoring.tests.test_probe.TestProbe.test_ok", ""),
                (
                    "openwisp_monitoring.db.backends.influxdb.tests.TestProbe.test_ok",
                    "",
                ),
                ("openwisp2.sample_monitoring.tests.TestProbe.test_ok", "1"),
            ):
                with self.subTest(label=label):
                    result = subprocess.run(
                        [str(root / "runtests"), label, "--noinput"],
                        cwd=root,
                        env={**os.environ, "SAMPLE_APP": ""},
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(
                        json.loads(result.stdout),
                        {"sample": sample, "args": ["test", label, "--noinput"]},
                    )


if __name__ == "__main__":
    unittest.main()
