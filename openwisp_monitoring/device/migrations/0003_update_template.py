# Manually Created

from django.db import migrations

from . import (
    TEMPLATE_CRONTAB_MONITORING_02,
    TEMPLATE_MONITORING_UUID,
    TEMPLATE_NETJSON_MONITORING_02,
    TEMPLATE_OPENWISP_MONITORING_02,
    TEMPLATE_POST_RELOAD_HOOK_02,
    TEMPLATE_RC_LOCAL_02,
)


def migrate_data(apps, schema_editor):
    Template = apps.get_model('config', 'Template')
    try:
        template = Template.objects.get(pk=TEMPLATE_MONITORING_UUID)
        template.config['files'][0] = TEMPLATE_OPENWISP_MONITORING_02
        template.config['files'][1] = TEMPLATE_NETJSON_MONITORING_02
        template.config['files'][2] = TEMPLATE_CRONTAB_MONITORING_02
        template.config['files'][3] = TEMPLATE_RC_LOCAL_02
        template.config['files'][5] = TEMPLATE_POST_RELOAD_HOOK_02
        template.config['openwisp'][0]['included_interfaces'] = '*'
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
