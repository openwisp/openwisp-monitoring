from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("sample_device_monitoring", "0002_add_group_permissions"),
        ("geo", "0003_alter_devicelocation_floorplan_location"),
    ]

    operations = [
        migrations.CreateModel(
            name="Map",
            fields=[],
            options={
                "abstract": False,
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=("geo.location",),
        ),
    ]
