import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.test import SimpleTestCase, override_settings

from openwisp_utils.tests import capture_stdout


class TestStaticFiles(SimpleTestCase):
    @capture_stdout()
    def test_collectstatic(self):
        """Ensures the staticfile backend used in the installers is happy"""
        app_dir = Path(__file__).resolve().parents[1]
        assets = (
            (
                app_dir / "device/static/monitoring/js/lib/leaflet.fullscreen.min.js",
                "monitoring/js/lib/leaflet.fullscreen.min.js",
            ),
            (
                app_dir / "device/static/monitoring/js/lib/netjsongraph.min.js",
                "monitoring/js/lib/netjsongraph.min.js",
            ),
            (
                app_dir / "device/static/monitoring/js/lib/moment.min.js",
                "monitoring/js/lib/moment.min.js",
            ),
            (
                app_dir / "device/static/monitoring/css/netjsongraph.css",
                "monitoring/css/netjsongraph.css",
            ),
            (
                app_dir / "device/static/monitoring/css/loading.gif",
                "monitoring/css/loading.gif",
            ),
            (
                app_dir / "monitoring/static/monitoring/js/lib/plotly-cartesian.min.js",
                "monitoring/js/lib/plotly-cartesian.min.js",
            ),
        )
        with TemporaryDirectory() as static_root, TemporaryDirectory() as staticfiles_dir:
            staticfiles_dir = Path(staticfiles_dir)
            for source, target in assets:
                destination = staticfiles_dir / target
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(source, destination)
            with override_settings(
                STATIC_ROOT=static_root,
                STATICFILES_DIRS=[staticfiles_dir],
                STATICFILES_FINDERS=[
                    "django.contrib.staticfiles.finders.FileSystemFinder"
                ],
                STORAGES={
                    "staticfiles": {
                        "BACKEND": "openwisp_utils.storage.CompressStaticFilesStorage"
                    }
                },
            ):
                call_command("collectstatic", interactive=False)
