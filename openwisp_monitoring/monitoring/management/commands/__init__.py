from django.core.management.base import BaseCommand

from ...tasks import migrate_timeseries_database


class BaseMigrateTimeseriesCommand(BaseCommand):
    help = 'Migrate timeseries database asynchronously'

    def handle(self, *args, **options):
        migrate_timeseries_database.delay()
