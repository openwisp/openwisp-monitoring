from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase


class TestManagementCommands(TestCase):
    @patch('openwisp_monitoring.monitoring.tasks.migrate_timeseries_database.delay')
    def test_migrate_timeseries(self, mocked_celery_task):
        call_command('migrate_timeseries')
        mocked_celery_task.assert_called_once()
