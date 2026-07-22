from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from .. import tasks


class TestManagementCommands(TestCase):
    @patch("openwisp_monitoring.monitoring.tasks.migrate_timeseries_database.delay")
    def test_migrate_timeseries(self, mocked_celery_task):
        call_command("migrate_timeseries")
        mocked_celery_task.assert_called_once()

    @patch(
        "openwisp_monitoring.monitoring.migrations.influxdb."
        "influxdb_alter_structure_0006.migrate_influxdb_structure"
    )
    def test_migrate_timeseries_task_skips_non_influxdb_backends(self, mocked_helper):
        with patch.object(tasks.timeseries_db, "backend_name", "influxdb2"):
            tasks.migrate_timeseries_database()
        mocked_helper.assert_not_called()
