import swapper
from django.contrib.auth.models import Permission

from openwisp_controller.migrations import create_default_permissions, get_swapped_model


def assign_permissions_to_groups(apps, schema_editor):
    create_default_permissions(apps, schema_editor)
    operators_read_only_admins_manage = [
        'check',
        'alertsettings',
        'wificlient',
        'wifisession',
    ]
    manage_operations = ['add', 'change', 'delete']
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
            permission = Permission.objects.get(codename='view_{}'.format(model_name))
            operator.permissions.add(permission.pk)
        except Permission.DoesNotExist:
            pass
        for operation in manage_operations:
            admin.permissions.add(
                Permission.objects.get(
                    codename='{}_{}'.format(operation, model_name)
                ).pk
            )


def assign_alertsettings_inline_permissions_to_groups(apps, schema_editor):
    create_default_permissions(apps, schema_editor)
    operators_read_only_admins_manage = [
        'alertsettings',
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


def create_general_metrics(apps, schema_editor):
    Chart = swapper.load_model('monitoring', 'Chart')
    Metric = swapper.load_model('monitoring', 'Metric')

    metric, created = Metric._get_or_create(
        configuration='general_clients',
        name='General Clients',
        key='wifi_clients',
        object_id=None,
        content_type_id=None,
    )
    if created:
        chart = Chart(metric=metric, configuration='gen_wifi_clients')
        chart.full_clean()
        chart.save()

    metric, created = Metric._get_or_create(
        configuration='general_traffic',
        name='General Traffic',
        key='traffic',
        object_id=None,
        content_type_id=None,
    )
    if created:
        chart = Chart(metric=metric, configuration='general_traffic')
        chart.full_clean()
        chart.save()


def delete_general_metrics(apps, schema_editor):
    Metric = apps.get_model('monitoring', 'Metric')
    Metric.objects.filter(content_type__isnull=True, object_id__isnull=True).delete()
