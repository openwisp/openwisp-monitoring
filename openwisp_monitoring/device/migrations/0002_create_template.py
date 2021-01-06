# Generated by Django 3.1.2 on 2020-12-20 06:15

import uuid
from collections import OrderedDict

from django.db import migrations
from django.db.models import Q

from . import (
    TEMPLATE_CRONTAB_MONITORING_01,
    TEMPLATE_MONITORING_UUID,
    TEMPLATE_NETJSON_MONITORING_01,
    TEMPLATE_OPENWISP_MONITORING_01,
    TEMPLATE_POST_RELOAD_HOOK_01,
    TEMPLATE_RC_LOCAL_01,
    TEMPLATE_UPDATE_OPENWISP_PACKAGES_01,
)


def migrate_data(apps, schema_editor):
    Template = apps.get_model('config', 'Template')
    if Template.objects.filter(
        Q(config__contains='/usr/sbin/openwisp-monitoring')
        & Q(config__contains='/usr/sbin/netjson-monitoring'),
    ).exists():
        return
    default_template = Template(
        pk=uuid.UUID(TEMPLATE_MONITORING_UUID),
        name='Monitoring (default)',
        default=True,
        organization=None,
        backend='netjsonconfig.OpenWrt',
        config=OrderedDict(
            {
                'files': [
                    TEMPLATE_OPENWISP_MONITORING_01,
                    TEMPLATE_NETJSON_MONITORING_01,
                    TEMPLATE_CRONTAB_MONITORING_01,
                    TEMPLATE_RC_LOCAL_01,
                    TEMPLATE_UPDATE_OPENWISP_PACKAGES_01,
                    TEMPLATE_POST_RELOAD_HOOK_01,
                ],
                'openwisp': [
                    OrderedDict(
                        {
                            'config_name': 'monitoring',
                            'config_value': 'monitoring',
                            'included_interface': 'tun0 tap0 tap1 wlan0 wlan1 br-lan eth1',
                        }
                    )
                ],
            }
        ),
    )
    default_template.full_clean()
    default_template.save()


class Migration(migrations.Migration):

    dependencies = [
        ('device_monitoring', '0001_squashed_0002_devicemonitoring'),
    ]

    operations = [
        migrations.RunPython(migrate_data, reverse_code=migrations.RunPython.noop)
    ]
