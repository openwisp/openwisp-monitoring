# Generated by Django 3.2.14 on 2022-08-12 07:50

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('check', '0007_create_checks'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='check',
            options={
                'permissions': (
                    ('add_check_inline', 'Can add check inline'),
                    ('change_check_inline', 'Can change check inline'),
                    ('delete_check_inline', 'Can delete check inline'),
                    ('view_check_inline', 'Can view check inline'),
                )
            },
        ),
    ]