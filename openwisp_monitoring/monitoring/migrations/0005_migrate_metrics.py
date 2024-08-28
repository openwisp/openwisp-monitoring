# Manually created

import logging

from django.db import migrations

from .influxdb.influxdb_alter_structure_0006 import (
    update_metric_timeseries_structure_forward_migration,
    update_metric_timeseries_structure_reverse_migration,
)

CHUNK_SIZE = 1000

logger = logging.getLogger(__name__)


class Migration(migrations.Migration):
    dependencies = [('monitoring', '0004_metric_main_and_extra_tags')]

    operations = [
        migrations.RunPython(
            update_metric_timeseries_structure_forward_migration,
            reverse_code=update_metric_timeseries_structure_reverse_migration,
        )
    ]
