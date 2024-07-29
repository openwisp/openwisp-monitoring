# Manually created

import logging

from django.db import migrations

from .influxdb.influxdb_alter_structure_0006 import (
    update_metric_timeseries_structure_forward_migration,
    update_metric_timeseries_structure_reverse_migration,
)

CHUNK_SIZE = 1000

logger = logging.getLogger(__name__)


def forward_migration(apps, schema_editor):
    update_metric_timeseries_structure_forward_migration(apps, schema_editor)
    from ..tasks import migrate_timeseries_database

    migrate_timeseries_database.delay()


def reverse_migration(apps, schema_editor):
    update_metric_timeseries_structure_reverse_migration(
        apps, schema_editor, metric_keys=['signal']
    )


class Migration(migrations.Migration):
    dependencies = [('monitoring', '0011_alter_metric_field_name')]

    operations = [
        migrations.RunPython(
            forward_migration,
            reverse_code=reverse_migration,
        )
    ]
