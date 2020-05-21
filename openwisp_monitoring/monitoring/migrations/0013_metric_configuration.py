# Generated by Django 3.0.3 on 2020-05-21 22:00

from django.db import migrations, models
from ..metrics import get_metric_configuration_choices


class Migration(migrations.Migration):

    dependencies = [
        ('monitoring', '0012_rename_graph_chart'),
    ]

    operations = [
        migrations.AddField(
            model_name='metric',
            name='configuration',
            field=models.CharField(
                choices=get_metric_configuration_choices(), max_length=16, null=True,
            ),
        ),
        migrations.RemoveField(model_name='metric', name='description'),
    ]
