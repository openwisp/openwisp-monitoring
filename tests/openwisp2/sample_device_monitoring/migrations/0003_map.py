from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('sample_device_monitoring', '0002_auto_20200429_1754'),
        ('openwisp_controller_geo', '0004_default_groups'),
    ]

    operations = [
        migrations.CreateModel(
            name='Map',
            fields=[],
            options={
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('geo.location',),
        ),
    ]
