# Generated by Django 3.2.18 on 2023-04-20 11:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('device_monitoring', '0006_alter_wificlient_field_ht_vht'),
    ]

    operations = [
        migrations.AddField(
            model_name='wificlient',
            name='he',
            field=models.BooleanField(
                blank=True, default=False, null=True, verbose_name='HE'
            ),
        ),
    ]
