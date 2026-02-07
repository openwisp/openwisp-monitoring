from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("sample_device_monitoring", "0002_add_group_permissions"),
    ]

    operations = [
        migrations.CreateModel(
            name="Map",
            fields=[],
            options={
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=("geo.location",),
        ),
    ]
