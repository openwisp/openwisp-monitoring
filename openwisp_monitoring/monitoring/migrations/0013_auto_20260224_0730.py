from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('monitoring', '0012_migrate_signal_metrics'),
    ]

    operations = [
        migrations.RunSQL(
            sql='DROP INDEX IF EXISTS monitoring_metric_main_tags_2d8550ae_like; '
                'DROP INDEX IF EXISTS monitoring_metric_main_tags_2d8550ae;',
            reverse_sql=migrations.RunSQL.noop
        ),
        migrations.RunSQL(
            sql='ALTER TABLE monitoring_metric ALTER COLUMN main_tags TYPE jsonb USING main_tags::jsonb; '
                'ALTER TABLE monitoring_metric ALTER COLUMN extra_tags TYPE jsonb USING extra_tags::jsonb;',
            reverse_sql='ALTER TABLE monitoring_metric ALTER COLUMN main_tags TYPE text; '
                        'ALTER TABLE monitoring_metric ALTER COLUMN extra_tags TYPE text;'
        ),
        migrations.RunSQL(
            sql='CREATE INDEX IF NOT EXISTS main_tags_gin_idx ON monitoring_metric USING gin (main_tags); '
                'CREATE INDEX IF NOT EXISTS extra_tags_gin_idx ON monitoring_metric USING gin (extra_tags);',
            reverse_sql='DROP INDEX IF EXISTS main_tags_gin_idx; DROP INDEX IF EXISTS extra_tags_gin_idx;'
        ),
    ]