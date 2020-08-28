# Generated by Django 3.0.5 on 2020-05-27 03:04

import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import model_utils.fields
import uuid
import swapper

from openwisp_monitoring.monitoring.configuration import (
    get_metric_configuration_choices,
    get_chart_configuration_choices,
)


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='Metric',
            fields=[
                (
                    'id',
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    'created',
                    model_utils.fields.AutoCreatedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name='created',
                    ),
                ),
                (
                    'modified',
                    model_utils.fields.AutoLastModifiedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name='modified',
                    ),
                ),
                ('name', models.CharField(max_length=64)),
                (
                    'configuration',
                    models.CharField(
                        choices=get_metric_configuration_choices(),
                        max_length=16,
                        null=True,
                    ),
                ),
                (
                    'key',
                    models.SlugField(
                        blank=True,
                        help_text='leave blank to determine automatically',
                        max_length=64,
                    ),
                ),
                ('field_name', models.CharField(default='value', max_length=16)),
                (
                    'object_id',
                    models.CharField(blank=True, db_index=True, max_length=36),
                ),
                (
                    'is_healthy',
                    models.BooleanField(
                        blank=True, db_index=True, default=None, null=True
                    ),
                ),
                ('details', models.CharField(blank=True, max_length=64, null=True)),
                (
                    'content_type',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to='contenttypes.ContentType',
                    ),
                ),
            ],
            options={
                'abstract': False,
                'unique_together': {('key', 'field_name', 'content_type', 'object_id')},
            },
        ),
        migrations.CreateModel(
            name='Chart',
            fields=[
                (
                    'id',
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    'created',
                    model_utils.fields.AutoCreatedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name='created',
                    ),
                ),
                (
                    'modified',
                    model_utils.fields.AutoLastModifiedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name='modified',
                    ),
                ),
                (
                    'configuration',
                    models.CharField(
                        choices=get_chart_configuration_choices(),
                        max_length=16,
                        null=True,
                    ),
                ),
                ('details', models.CharField(blank=True, max_length=64, null=True)),
                (
                    'metric',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=swapper.get_model_name('monitoring', 'Metric'),
                    ),
                ),
            ],
            options={'abstract': False,},
        ),
        migrations.CreateModel(
            name='AlertSettings',
            fields=[
                (
                    'id',
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    'created',
                    model_utils.fields.AutoCreatedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name='created',
                    ),
                ),
                (
                    'modified',
                    model_utils.fields.AutoLastModifiedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name='modified',
                    ),
                ),
                (
                    'custom_operator',
                    models.CharField(
                        blank=True,
                        choices=[('<', 'less than'), ('>', 'greater than')],
                        max_length=1,
                        null=True,
                        verbose_name='operator',
                    ),
                ),
                (
                    'custom_threshold',
                    models.FloatField(
                        blank=True,
                        help_text='threshold value',
                        null=True,
                        verbose_name='threshold value',
                    ),
                ),
                (
                    'custom_tolerance',
                    models.PositiveIntegerField(
                        blank=True,
                        help_text='for how many minutes should the threshold value be crossed before an alert is sent? A value of zero means the alert is sent immediately',
                        null=True,
                        validators=[django.core.validators.MaxValueValidator(10080)],
                        verbose_name='threshold tolerance',
                    ),
                ),
                ('details', models.CharField(blank=True, max_length=64, null=True)),
                (
                    'metric',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=swapper.get_model_name('monitoring', 'Metric'),
                    ),
                ),
                (
                    'is_active',
                    models.BooleanField(
                        default=True,
                        help_text=(
                            'whether alerts are enabled for this metric, uncheck to '
                            'disable this alert for this object and all users'
                        ),
                        verbose_name='Alerts enabled',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Alert settings',
                'verbose_name_plural': 'Alert settings',
                'abstract': False,
            },
        ),
    ]
