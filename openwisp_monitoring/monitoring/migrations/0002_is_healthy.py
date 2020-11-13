from django.db import migrations, models


def forward(apps, schema_editor):
    Metric = apps.get_model('monitoring', 'Metric')
    for metric in Metric.objects.all():
        metric.is_healthy = metric.health == 'ok'
        metric.save()


def backward(apps, schema_editor):
    Metric = apps.get_model('monitoring', 'Metric')
    for metric in Metric.objects.all():
        metric.health = 'ok' if metric.is_healthy else 'problem'
        metric.save()


class Migration(migrations.Migration):
    dependencies = [('monitoring', '0001_initial')]
    operations = [
        migrations.AddField(
            model_name='metric',
            name='is_healthy',
            field=models.BooleanField(db_index=True, default=True),
        ),
        migrations.RunPython(forward, reverse_code=backward),
        migrations.RemoveField(model_name='metric', name='health'),
    ]
