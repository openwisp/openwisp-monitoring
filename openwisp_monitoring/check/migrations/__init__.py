from django.contrib.auth.models import Permission

from openwisp_controller.migrations import create_default_permissions, get_swapped_model


def assign_check_inline_permissions_to_groups(apps, schema_editor):
    create_default_permissions(apps, schema_editor)
    operators_read_only_admins_manage = [
        'check',
    ]
    manage_operations = ['add', 'view', 'change', 'delete']
    Group = get_swapped_model(apps, 'openwisp_users', 'Group')

    try:
        admin = Group.objects.get(name='Administrator')
        operator = Group.objects.get(name='Operator')
    # consider failures custom cases
    # that do not have to be dealt with
    except Group.DoesNotExist:
        return

    for model_name in operators_read_only_admins_manage:
        try:
            permission = Permission.objects.get(
                codename='view_{}_inline'.format(model_name)
            )
            operator.permissions.add(permission.pk)
        except Permission.DoesNotExist:
            pass
        for operation in manage_operations:
            permission = Permission.objects.get(
                codename='{}_{}_inline'.format(operation, model_name)
            )
            admin.permissions.add(permission.pk)
