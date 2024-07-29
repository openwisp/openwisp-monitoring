# Manually Created

from collections import OrderedDict

from django.db import migrations

from . import (
    TEMPLATE_CRONTAB_MONITORING_02,
    TEMPLATE_MONITORING_UUID,
    TEMPLATE_NETJSON_MONITORING_02,
    TEMPLATE_OPENWISP_MONITORING_02,
    TEMPLATE_POST_RELOAD_HOOK_02,
    TEMPLATE_RC_LOCAL_02,
    TEMPLATE_UPDATE_OPENWISP_PACKAGES_02,
)


def migrate_data(apps, schema_editor):
    Template = apps.get_model('config', 'Template')
    try:
        template = Template.objects.get(pk=TEMPLATE_MONITORING_UUID)
        template.config = OrderedDict(
            {
                'files': [
                    TEMPLATE_OPENWISP_MONITORING_02,
                    TEMPLATE_NETJSON_MONITORING_02,
                    TEMPLATE_CRONTAB_MONITORING_02,
                    TEMPLATE_RC_LOCAL_02,
                    TEMPLATE_UPDATE_OPENWISP_PACKAGES_02,
                    TEMPLATE_POST_RELOAD_HOOK_02,
                ],
                'openwisp': [
                    OrderedDict(
                        {
                            'config_name': 'monitoring',
                            'config_value': 'monitoring',
                            'included_interfaces': '*',
                        }
                    )
                ],
            }
        )
        template.full_clean()
        template.save()
    except Template.DoesNotExist:
        pass


class Migration(migrations.Migration):
    dependencies = [
        ('device_monitoring', '0002_create_template'),
    ]

    operations = [
        migrations.RunPython(migrate_data, reverse_code=migrations.RunPython.noop)
    ]
