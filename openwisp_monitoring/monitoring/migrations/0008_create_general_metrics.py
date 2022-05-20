# Manually created
from django.db import migrations

from . import create_general_metric, delete_general_metric


class Migration(migrations.Migration):

    dependencies = [('monitoring', '0007_alter_metric_object_id')]

    operations = [
        migrations.RunPython(create_general_metric, reverse_code=delete_general_metric)
    ]
