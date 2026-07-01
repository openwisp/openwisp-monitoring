# Manually created
from django.db import migrations

from openwisp_monitoring.db import timeseries_db


def forward_migration(apps, schema_editor):

    if timeseries_db.backend_name != "influxdb":
        return

    from ..tasks import migrate_timeseries_database

    migrate_timeseries_database.delay()


class Migration(migrations.Migration):
    dependencies = [("monitoring", "0005_migrate_metrics")]

    operations = [
        migrations.RunPython(forward_migration, reverse_code=migrations.RunPython.noop)
    ]
