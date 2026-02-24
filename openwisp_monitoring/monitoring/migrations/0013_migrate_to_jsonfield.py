import django.contrib.postgres.indexes
from django.db import migrations, models


def migrate_to_jsonb(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "DROP INDEX IF EXISTS monitoring_metric_main_tags_2d8550ae_like; "
            "DROP INDEX IF EXISTS monitoring_metric_main_tags_2d8550ae;"
        )
        cursor.execute(
            "ALTER TABLE monitoring_metric ALTER COLUMN main_tags TYPE jsonb USING main_tags::jsonb; "
            "ALTER TABLE monitoring_metric ALTER COLUMN extra_tags TYPE jsonb USING extra_tags::jsonb;"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS main_tags_gin_idx ON monitoring_metric USING gin (main_tags); "
            "CREATE INDEX IF NOT EXISTS extra_tags_gin_idx ON monitoring_metric USING gin (extra_tags);"
        )


def rollback_jsonb(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "DROP INDEX IF EXISTS main_tags_gin_idx; DROP INDEX IF EXISTS extra_tags_gin_idx;"
        )
        cursor.execute(
            "ALTER TABLE monitoring_metric ALTER COLUMN main_tags TYPE text; "
            "ALTER TABLE monitoring_metric ALTER COLUMN extra_tags TYPE text;"
        )


class Migration(migrations.Migration):
    dependencies = [
        ("monitoring", "0012_migrate_signal_metrics"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name="metric",
                    name="extra_tags",
                    field=models.JSONField(
                        blank=True,
                        default=dict,
                        verbose_name="extra tags",
                    ),
                ),
                migrations.AlterField(
                    model_name="metric",
                    name="main_tags",
                    field=models.JSONField(
                        blank=True,
                        db_index=True,
                        default=dict,
                        verbose_name="main tags",
                    ),
                ),
                migrations.AddIndex(
                    model_name="metric",
                    index=django.contrib.postgres.indexes.GinIndex(
                        fields=["main_tags"],
                        name="main_tags_gin_idx",
                    ),
                ),
                migrations.AddIndex(
                    model_name="metric",
                    index=django.contrib.postgres.indexes.GinIndex(
                        fields=["extra_tags"],
                        name="extra_tags_gin_idx",
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(migrate_to_jsonb, reverse_code=rollback_jsonb),
            ],
        ),
    ]
