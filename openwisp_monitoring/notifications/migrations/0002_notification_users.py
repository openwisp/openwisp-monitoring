from django.conf import settings
from django.db import migrations


def create_notificationuser_settings(apps, schema_editor):
    """
    Data migration
    """
    NotificationUser = apps.get_model('notifications', 'NotificationUser')
    User = apps.get_model(*settings.AUTH_USER_MODEL.split('.'))
    for user in User.objects.all():
        notification_settings = NotificationUser(user=user)
        notification_settings.full_clean()
        notification_settings.save()


class Migration(migrations.Migration):
    dependencies = [
        ('notifications', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.RunPython(
            create_notificationuser_settings,
            reverse_code=migrations.RunPython.noop
        ),
    ]
