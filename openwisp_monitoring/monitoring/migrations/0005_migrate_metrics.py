# Manually created

import logging

from django.core.exceptions import ObjectDoesNotExist
from django.db import migrations
from swapper import load_model

EXCLUDED_MEASUREMENTS = [
    'ping',
    'config_applied',
    'clients',
    'disk',
    'memory',
    'cpu',
    'signal_strength',
    'signal_quality',
    'access_tech',
    'device_data',
    'traffic',
    'wifi_clients',
]
CHUNK_SIZE = 1000

logger = logging.getLogger(__name__)


def forward_migrate_metric(metric_model, configuration, new_key):
    metric_qs = metric_model.objects.filter(configuration=configuration).exclude(
        key__in=EXCLUDED_MEASUREMENTS
    )
    updated_metrics = []
    for metric in metric_qs.iterator(chunk_size=CHUNK_SIZE):
        extra_tags = {
            'ifname': metric.key,
        }
        try:
            extra_tags.update(
                {'organization_id': str(metric.content_object.organization_id)}
            )
        except ObjectDoesNotExist:
            pass
        metric.extra_tags.update(extra_tags)
        metric.key = new_key
        updated_metrics.append(metric)
        if len(updated_metrics) > CHUNK_SIZE:
            metric_model.objects.bulk_update(
                updated_metrics, fields=['extra_tags', 'key']
            )
            updated_metrics = []
    if updated_metrics:
        metric_model.objects.bulk_update(updated_metrics, fields=['extra_tags', 'key'])


def forward_migration(apps, schema_editor):
    Metric = load_model('monitoring', 'Metric')
    forward_migrate_metric(Metric, configuration='clients', new_key='wifi_clients')
    forward_migrate_metric(Metric, configuration='traffic', new_key='traffic')


def reverse_migration(apps, schema_editor):
    # Reverse migration is required because of the
    # the unique together condition implemented in
    # Metric model.
    Metric = load_model('monitoring', 'Metric')
    updated_metrics = []
    for metric in Metric.objects.filter(key__in=['traffic', 'wifi_clients']).iterator(
        chunk_size=CHUNK_SIZE
    ):
        metric.key = metric.extra_tags['ifname']
        updated_metrics.append(metric)
        if len(updated_metrics) > CHUNK_SIZE:
            Metric.objects.bulk_update(updated_metrics, fields=['key'])
            updated_metrics = []
    if updated_metrics:
        Metric.objects.bulk_update(updated_metrics, fields=['key'])


class Migration(migrations.Migration):

    dependencies = [('monitoring', '0004_metric_extra_tags')]

    operations = [
        migrations.RunPython(forward_migration, reverse_code=reverse_migration)
    ]
