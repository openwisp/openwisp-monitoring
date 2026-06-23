# Manually created
# Updates signal metric names to include the interface name (ifname) prefix
# for the sample_monitoring app (mirrors 0014 in the main monitoring app).

import logging

from django.db import migrations

CHUNK_SIZE = 1000

logger = logging.getLogger(__name__)

SIGNAL_CONFIGURATIONS = {
    "signal_strength": "signal strength",
    "signal_quality": "signal quality",
    "access_tech": "access technology",
}


def forward_migration(apps, schema_editor):
    Metric = apps.get_model("sample_monitoring", "Metric")
    updated_metrics = []
    for configuration, old_suffix in SIGNAL_CONFIGURATIONS.items():
        metric_qs = Metric.objects.filter(
            configuration=configuration,
            name=old_suffix,
        )
        for metric in metric_qs.iterator(chunk_size=CHUNK_SIZE):
            ifname = metric.main_tags.get("ifname", "")
            if ifname:
                metric.name = f"{ifname} {old_suffix}"
                updated_metrics.append(metric)
                if len(updated_metrics) >= CHUNK_SIZE:
                    Metric.objects.bulk_update(updated_metrics, fields=["name"])
                    updated_metrics = []
    if updated_metrics:
        Metric.objects.bulk_update(updated_metrics, fields=["name"])
    logger.info(
        "Signal metric name migration (forward) completed for sample_monitoring."
    )


def reverse_migration(apps, schema_editor):
    Metric = apps.get_model("sample_monitoring", "Metric")
    updated_metrics = []
    for configuration, old_suffix in SIGNAL_CONFIGURATIONS.items():
        metric_qs = Metric.objects.filter(configuration=configuration)
        for metric in metric_qs.iterator(chunk_size=CHUNK_SIZE):
            ifname = metric.main_tags.get("ifname", "")
            expected_new_name = f"{ifname} {old_suffix}" if ifname else old_suffix
            if metric.name == expected_new_name:
                metric.name = old_suffix
                updated_metrics.append(metric)
                if len(updated_metrics) >= CHUNK_SIZE:
                    Metric.objects.bulk_update(updated_metrics, fields=["name"])
                    updated_metrics = []
    if updated_metrics:
        Metric.objects.bulk_update(updated_metrics, fields=["name"])
    logger.info(
        "Signal metric name migration (reverse) completed for sample_monitoring."
    )


class Migration(migrations.Migration):
    dependencies = [("sample_monitoring", "0005_replace_jsonfield_with_django_builtin")]

    operations = [
        migrations.RunPython(
            forward_migration,
            reverse_code=reverse_migration,
        )
    ]
