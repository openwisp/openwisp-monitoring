from django.db import migrations


def populate_is_healthy_tolerant(apps, schema_editor):
    Metric = apps.get_model('monitoring', 'Metric')
    chunk_size = 2000
    metrics = []
    for metric in (
        Metric.objects.filter(is_healthy__isnull=False)
        .only('id', 'is_healthy')
        .iterator(chunk_size=chunk_size)
    ):
        metric.is_healthy_tolerant = metric.is_healthy
        metrics.append(metric)
        if len(metrics) == chunk_size:
            Metric.objects.bulk_update(metrics, fields=['is_healthy_tolerant'])
            metrics = []
    if metrics:
        Metric.objects.bulk_update(metrics, fields=['is_healthy_tolerant'])


class Migration(migrations.Migration):
    dependencies = [
        ('monitoring', '0002_metric_is_healthy_tolerance'),
    ]

    operations = [
        migrations.RunPython(
            populate_is_healthy_tolerant, reverse_code=migrations.RunPython.noop
        ),
    ]
