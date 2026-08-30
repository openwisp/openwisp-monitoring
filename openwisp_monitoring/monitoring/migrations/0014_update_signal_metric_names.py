# Manually created
# Updates signal metric names to include the interface name (ifname) prefix,
# matching the new naming convention introduced by writer.py which now uses
# "{ifname} signal strength", "{ifname} signal quality", "{ifname} access technology"
# instead of the old static names "signal strength", "signal quality", "access technology".

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
    """
    Update old signal metric names to include the interface name.
    e.g. "signal strength" → "mobile0 signal strength"
    """
    Metric = apps.get_model("monitoring", "Metric")
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
                    logger.info(
                        f"Bulk updated {len(updated_metrics)} signal metric names."
                    )
                    updated_metrics = []
    if updated_metrics:
        Metric.objects.bulk_update(updated_metrics, fields=["name"])
        logger.info(f"Bulk updated {len(updated_metrics)} signal metric names.")
    logger.info("Signal metric name migration (forward) completed.")


def reverse_migration(apps, schema_editor):
    """
    Revert signal metric names back to the old static names.
    e.g. "mobile0 signal strength" → "signal strength"
    """
    Metric = apps.get_model("monitoring", "Metric")
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
    logger.info("Signal metric name migration (reverse) completed.")


class Migration(migrations.Migration):
    dependencies = [("monitoring", "0013_replace_jsonfield_with_django_builtin")]

    operations = [
        migrations.RunPython(
            forward_migration,
            reverse_code=reverse_migration,
        )
    ]
