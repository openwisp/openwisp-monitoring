# Generated by Django 3.0.3 on 2020-05-21 22:00

from django.db import migrations, models

from ..configuration import METRIC_CONFIGURATION_CHOICES


class Migration(migrations.Migration):

    dependencies = [
        ('monitoring', '0015_delete_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='metric',
            name='configuration',
            field=models.CharField(
                choices=METRIC_CONFIGURATION_CHOICES, max_length=16, null=True,
            ),
        ),
        migrations.RemoveField(model_name='metric', name='description'),
    ]
