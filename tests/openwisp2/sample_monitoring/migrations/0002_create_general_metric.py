from django.db import migrations

from openwisp_monitoring.monitoring.migrations import (
    create_general_metrics,
    delete_general_metrics,
)


class Migration(migrations.Migration):

    dependencies = [('sample_monitoring', '0001_initial')]

    operations = [
        migrations.RunPython(
            create_general_metrics, reverse_code=delete_general_metrics
        )
    ]
