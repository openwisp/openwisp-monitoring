from django.db import migrations

graph_mapping = {
    'uptime': 'uptime',
    'packet loss': 'packet_loss',
    'round trip time': 'rtt',
    'traffic': 'traffic',
    'clients': 'wifi_clients',
}


def find_graph_configuration(title):
    title_lowercase = title.lower()
    for key, value in graph_mapping.items():
        if key in title_lowercase:
            return value
    raise ValueError(f'no graph configuration found for {title}')


def fill_configuration(apps, schema_editor):
    Graph = apps.get_model('monitoring', 'Graph')
    for graph in Graph.objects.all():
        graph.configuration = find_graph_configuration(graph.description)
        graph.full_clean()
        graph.save()


class Migration(migrations.Migration):

    dependencies = [('monitoring', '0006_add_configuration')]

    operations = [
        migrations.RunPython(fill_configuration, reverse_code=migrations.RunPython.noop)
    ]
