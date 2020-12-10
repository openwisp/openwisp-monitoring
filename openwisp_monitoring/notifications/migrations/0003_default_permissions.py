from django.contrib.auth.management import create_permissions
from django.contrib.auth.models import Permission
from django.db import migrations


def create_default_groups(apps, schema_editor):
    group = apps.get_model('openwisp_users', 'group')

    # To populate all the permissions
    for app_config in apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None

    operator = group.objects.filter(name='Operator')
    if operator.count() == 0:
        operator = group.objects.create(name='Operator')
    else:
        operator = operator.first()

    admin = group.objects.filter(name='Administrator')
    if admin.count() == 0:
        admin = group.objects.create(name='Administrator')
    else:
        admin = admin.first()
    permissions = [
        Permission.objects.get(
            content_type__app_label='notifications', codename='add_notification'
        ).pk,
        Permission.objects.get(
            content_type__app_label='notifications', codename='change_notification'
        ).pk,
        Permission.objects.get(
            content_type__app_label='notifications', codename='delete_notification'
        ).pk,
    ]
    permissions += operator.permissions.all()
    operator.permissions.set(permissions)

    permissions += admin.permissions.all()
    admin.permissions.set(permissions)


class Migration(migrations.Migration):
    dependencies = [('notifications', '0002_notification_users')]

    operations = [
        migrations.RunPython(
            create_default_groups, reverse_code=migrations.RunPython.noop
        )
    ]
