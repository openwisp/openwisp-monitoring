from django.db import migrations
import logging

from . import (
    TEMPLATE_MONITORING_UUID,
    TEMPLATE_NETJSON_MONITORING_02,
)


logger = logging.getLogger(__name__)


def migrate_data(apps, schema_editor):
    Template = apps.get_model('config', 'Template')
    try:
        template = Template.objects.get(pk=TEMPLATE_MONITORING_UUID)
        template.config['files'][1] = TEMPLATE_NETJSON_MONITORING_02
        template.full_clean()
        template.save()
    except Template.DoesNotExist:
        logger.error('Could not find default netjson monitoring script!')
    except Exception as e:
        logger.exception(e)

    return


class Migration(migrations.Migration):

    dependencies = [
        ('device_monitoring', '0002_create_template'),
    ]

    operations = [
        migrations.RunPython(migrate_data, reverse_code=migrations.RunPython.noop)
    ]
