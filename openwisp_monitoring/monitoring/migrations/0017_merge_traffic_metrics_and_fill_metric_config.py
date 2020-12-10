from django.db import migrations

metric_mapping = {
    'reachable': 'ping',
    'rx_bytes': 'traffic',
    'clients': 'clients',
    'used_disk': 'disk',
    'percent_used': 'memory',
    'cpu_usage': 'cpu',
}


def merge_traffic_metrics(apps, schema_editor):
    Metric = apps.get_model('monitoring', 'Metric')
    Chart = apps.get_model('monitoring', 'Chart')
    rx_metrics = Metric.objects.filter(field_name='rx_bytes')
    for rx_metric in rx_metrics:
        if rx_metric.name.split()[1] == 'traffic':
            return
        # Traffic chart is created with tx_bytes metric
        tx_metric = Metric.objects.get(
            name=f'{rx_metric.name.split()[0]} tx_bytes',
            object_id=rx_metric.object_id,
            content_type=rx_metric.content_type,
        )
        if tx_metric.chart_set.count():
            chart = Chart.objects.get(metric=tx_metric)
            new_name = f'{rx_metric.name.split()[0]} traffic'
            print(f'Renamed metric "{rx_metric.name}" to "{new_name}"')
            rx_metric.name = new_name
            rx_metric.save()
            chart.metric = rx_metric
            chart.save()
        tx_metric.delete()


def find_metric_configuration(field_name):
    try:
        value = metric_mapping[field_name]
        return value
    except KeyError:
        print(f'No metric configuration found for "{field_name}"')


def fill_configuration(apps, schema_editor):
    Metric = apps.get_model('monitoring', 'Metric')
    for metric in Metric.objects.all():
        metric.configuration = find_metric_configuration(metric.field_name)
        metric.full_clean()
        metric.save()


class Migration(migrations.Migration):

    dependencies = [('monitoring', '0016_metric_configuration')]

    operations = [
        migrations.RunPython(
            merge_traffic_metrics, reverse_code=migrations.RunPython.noop
        ),
        migrations.RunPython(
            fill_configuration, reverse_code=migrations.RunPython.noop
        ),
    ]
