# To migrate data from openwisp_monitoring.notifications to openwisp_notifications
from django.db import migrations


def migrate_data(apps, schema_editor):
    """
    Migrates data from models of openwisp_monitoring.notifications
    to models of openwisp_monitoring.
    """
    mtr_notification = apps.get_model('notifications', 'Notification')
    mtr_notification_user = apps.get_model('notifications', 'NotificationUser')
    owp_notification = apps.get_model('openwisp_notifications', 'Notification')
    owp_notification_user = apps.get_model('openwisp_notifications', 'NotificationUser')

    notification_qs = mtr_notification.objects.all()
    owp_notification.objects.bulk_create(notification_qs)

    notification_user_qs = mtr_notification_user.objects.all()
    owp_notification_user.objects.bulk_create(notification_user_qs)


def undo_migrate(apps, schema_editor):
    mtr_notification = apps.get_model('notifications', 'Notification')
    mtr_notification_user = apps.get_model('notifications', 'NotificationUser')
    owp_notification = apps.get_model('openwisp_notifications', 'Notification')
    owp_notification_user = apps.get_model('openwisp_notifications', 'NotificationUser')

    notification_qs = owp_notification.objects.all()
    mtr_notification.objects.bulk_create(notification_qs)

    notification_user_qs = owp_notification_user.objects.all()
    mtr_notification_user.objects.bulk_create(notification_user_qs)

    owp_notification.objects.all().delete()
    owp_notification_user.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0003_default_permissions'),
        ('openwisp_notifications', '0002_default_permissions'),
    ]

    operations = [migrations.RunPython(migrate_data, undo_migrate)]
