from django.db import migrations
from swapper import load_model


def merge_traffic_metrics(apps, schema_editor):
    Metric = load_model('monitoring', 'Metric')
    Chart = load_model('monitoring', 'Chart')
    rx_metrics = Metric.objects.filter(field_name='rx_bytes')
    for rx_metric in rx_metrics:
        # Traffic chart is created with tx_bytes metric
        tx_metric = Metric.objects.get(name=f'{rx_metric.name.split()[0]} tx_bytes')
        chart = Chart.objects.get(metric=tx_metric)
        new_name = f'{rx_metric.name.split()[0]} traffic'
        print(f'Renamed metric "{rx_metric.name}" to "{new_name}"')
        rx_metric.name = new_name
        rx_metric.save()
        chart.metric = rx_metric
        chart.save()
        tx_metric.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('monitoring', '0013_metric_configuration'),
    ]

    operations = [
        migrations.RunPython(
            merge_traffic_metrics, reverse_code=migrations.RunPython.noop
        ),
    ]
