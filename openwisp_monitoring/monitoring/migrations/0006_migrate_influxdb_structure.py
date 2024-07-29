# Manually created
from django.db import migrations


def forward_migration(apps, schema_editor):
    from ..tasks import migrate_timeseries_database

    migrate_timeseries_database.delay()


class Migration(migrations.Migration):
    dependencies = [('monitoring', '0005_migrate_metrics')]

    operations = [
        migrations.RunPython(forward_migration, reverse_code=migrations.RunPython.noop)
    ]
