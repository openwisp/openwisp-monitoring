from datetime import timedelta

from django.core import mail
from django.test import TestCase
from django.utils import timezone
from django.utils.html import strip_tags
from swapper import load_model

from openwisp_controller.config.models import Config, Device
from openwisp_controller.config.tests import CreateConfigTemplateMixin
from openwisp_users.models import OrganizationUser

from ...monitoring.tests import TestMonitoringMixin

Notification = load_model('openwisp_notifications', 'Notification')
notification_queryset = Notification.objects.order_by('timestamp')
start_time = timezone.now()
ten_minutes_ago = start_time - timedelta(minutes=10)


class TestNotifications(CreateConfigTemplateMixin, TestMonitoringMixin, TestCase):
    device_model = Device
    config_model = Config

    def test_general_check_alert_settings_crossed_immediate(self):
        admin = self._create_admin()
        m = self._create_general_metric(name='load')
        self._create_alert_settings(metric=m, operator='>', value=90, seconds=0)

        with self.subTest("Test notification for metric exceeding alert settings"):
            m.write(99)
            self.assertFalse(m.is_healthy)
            self.assertEqual(Notification.objects.count(), 1)
            n = notification_queryset.first()
            self.assertEqual(n.recipient, admin)
            self.assertEqual(n.actor, m)
            self.assertEqual(n.action_object, m.alertsettings)
            self.assertEqual(n.level, 'warning')

        with self.subTest("Test no double alarm for metric exceeding alert settings"):
            m.write(95)
            self.assertFalse(m.is_healthy)
            self.assertEqual(Notification.objects.count(), 1)

        with self.subTest("Test notification for metric falling behind alert settings"):
            m.write(60)
            self.assertTrue(m.is_healthy)
            self.assertEqual(Notification.objects.count(), 2)
            n = notification_queryset.last()
            self.assertEqual(n.recipient, admin)
            self.assertEqual(n.actor, m)
            self.assertEqual(n.action_object, m.alertsettings)
            self.assertEqual(n.level, 'info')

        with self.subTest("Test no double alarm for metric falling behind alert settings"):
            m.write(40)
            self.assertTrue(m.is_healthy)
            self.assertEqual(Notification.objects.count(), 2)

    def test_general_check_alert_settings_crossed_deferred(self):
        admin = self._create_admin()
        m = self._create_general_metric(name='load')
        self._create_alert_settings(metric=m, operator='>', value=90, seconds=60)
        m.write(99, time=ten_minutes_ago)
        self.assertFalse(m.is_healthy)
        self.assertEqual(Notification.objects.count(), 1)
        n = notification_queryset.first()
        self.assertEqual(n.recipient, admin)
        self.assertEqual(n.actor, m)
        self.assertEqual(n.action_object, m.alertsettings)
        self.assertEqual(n.level, 'warning')

    def test_general_check_alert_settings_deferred_not_crossed(self):
        self._create_admin()
        m = self._create_general_metric(name='load')
        self._create_alert_settings(metric=m, operator='>', value=90, seconds=60)
        m.write(99)
        self.assertTrue(m.is_healthy)
        self.assertEqual(Notification.objects.count(), 0)

    def test_general_check_alert_settings_crossed_for_long_time(self):
        """
        this is going to be the most realistic scenario:
        incoming metrics will always be stored with the current
        timestamp, which means the system must be able to look
        back in previous measurements to see if the AlertSettings
        has been crossed for long enough
        """
        admin = self._create_admin()
        m = self._create_general_metric(name='load')
        self._create_alert_settings(metric=m, operator='>', value=90, seconds=61)

        with self.subTest("Test no notification is generated for healthy status"):
            m.write(89, time=ten_minutes_ago)
            self.assertTrue(m.is_healthy)
            self.assertEqual(Notification.objects.count(), 0)

        with self.subTest("Test no notification is generated when check=False"):
            m.write(91, time=ten_minutes_ago, check=False)
            self.assertEqual(Notification.objects.count(), 0)

        with self.subTest("Test notification for metric with current timestamp"):
            m.write(92)
            self.assertFalse(m.is_healthy)
            self.assertEqual(Notification.objects.count(), 1)
            n = notification_queryset.first()
            self.assertEqual(n.recipient, admin)
            self.assertEqual(n.actor, m)
            self.assertEqual(n.action_object, m.alertsettings)
            self.assertEqual(n.level, 'warning')

    def test_object_check_alert_settings_crossed_immediate(self):
        admin = self._create_admin()
        om = self._create_object_metric(name='load')
        alert_s = self._create_alert_settings(metric=om, operator='>', value=90, seconds=0)

        with self.subTest("Test notification for object metric exceeding alert settings"):
            om.write(99)
            self.assertFalse(om.is_healthy)
            self.assertEqual(Notification.objects.count(), 1)
            n = notification_queryset.first()
            self.assertEqual(n.recipient, admin)
            self.assertEqual(n.actor, om)
            self.assertEqual(n.action_object, alert_s)
            self.assertEqual(n.target, om.content_object)
            self.assertEqual(n.level, 'warning')

        with self.subTest("Test no double alarm for object metric exceeding alert settings"):
            om.write(95)
            self.assertFalse(om.is_healthy)
            self.assertEqual(Notification.objects.count(), 1)

        with self.subTest(
            "Test notification for object metric falling behind alert settings"
        ):
            om.write(60)
            self.assertTrue(om.is_healthy)
            self.assertEqual(Notification.objects.count(), 2)
            n = notification_queryset.last()
            self.assertEqual(n.recipient, admin)
            self.assertEqual(n.actor, om)
            self.assertEqual(n.action_object, alert_s)
            self.assertEqual(n.target, om.content_object)
            self.assertEqual(n.level, 'info')

        with self.subTest(
            "Test no double alarm for object metric falling behind alert settings"
        ):
            om.write(40)
            self.assertTrue(om.is_healthy)
            self.assertEqual(Notification.objects.count(), 2)

    def test_object_check_alert_settings_crossed_deferred(self):
        admin = self._create_admin()
        om = self._create_object_metric(name='load')
        alert_s = self._create_alert_settings(
            metric=om, operator='>', value=90, seconds=60
        )
        om.write(99, time=ten_minutes_ago)
        self.assertFalse(om.is_healthy)
        self.assertEqual(Notification.objects.count(), 1)
        n = notification_queryset.first()
        self.assertEqual(n.recipient, admin)
        self.assertEqual(n.actor, om)
        self.assertEqual(n.action_object, alert_s)
        self.assertEqual(n.target, om.content_object)
        self.assertEqual(n.level, 'warning')

    def test_object_check_alert_settings_deferred_not_crossed(self):
        self._create_admin()
        om = self._create_object_metric(name='load')
        self._create_alert_settings(metric=om, operator='>', value=90, seconds=60)
        om.write(99)
        self.assertTrue(om.is_healthy)
        self.assertEqual(Notification.objects.count(), 0)

    def test_object_check_alert_settings_crossed_for_long_time(self):
        admin = self._create_admin()
        om = self._create_object_metric(name='load')
        alert_s = self._create_alert_settings(
            metric=om, operator='>', value=90, seconds=61
        )
        om.write(89, time=ten_minutes_ago)
        self.assertEqual(Notification.objects.count(), 0)
        om.write(91, time=ten_minutes_ago, check=False)
        self.assertEqual(Notification.objects.count(), 0)
        om.write(92)
        self.assertFalse(om.is_healthy)
        self.assertEqual(Notification.objects.count(), 1)
        n = notification_queryset.first()
        self.assertEqual(n.recipient, admin)
        self.assertEqual(n.actor, om)
        self.assertEqual(n.action_object, alert_s)
        self.assertEqual(n.target, om.content_object)
        self.assertEqual(n.level, 'warning')
        # ensure double alarm not sent
        om.write(95)
        self.assertFalse(om.is_healthy)
        self.assertEqual(Notification.objects.count(), 1)
        # alert_settings back to normal
        om.write(60)
        self.assertTrue(om.is_healthy)
        self.assertEqual(Notification.objects.count(), 2)
        n = notification_queryset.last()
        self.assertEqual(n.recipient, admin)
        self.assertEqual(n.actor, om)
        self.assertEqual(n.action_object, alert_s)
        self.assertEqual(n.target, om.content_object)
        self.assertEqual(n.level, 'info')
        # ensure double alarm not sent
        om.write(40)
        self.assertTrue(om.is_healthy)
        self.assertEqual(Notification.objects.count(), 2)

    def test_general_metric_multiple_notifications(self):
        testorg = self._create_org()
        admin = self._create_admin()
        staff = self._create_user(
            username='staff', email='staff@staff.com', password='staff', is_staff=True
        )
        self._create_user(
            username='staff-lone',
            email='staff-lone@staff.com',
            password='staff',
            is_staff=True,
        )
        user = self._create_user(is_staff=False)
        OrganizationUser.objects.create(user=user, organization=testorg)
        OrganizationUser.objects.create(user=staff, organization=testorg)
        self.assertIsNotNone(staff.notificationuser)
        m = self._create_general_metric(name='load')
        alert_s = self._create_alert_settings(metric=m, operator='>', value=90, seconds=61)
        m._notify_users(notification_type='default', alert_settings=alert_s)
        self.assertEqual(Notification.objects.count(), 1)
        n = notification_queryset.first()
        self.assertEqual(n.recipient, admin)
        self.assertEqual(n.actor, m)
        self.assertEqual(n.target, None)
        self.assertEqual(n.action_object, m.alertsettings)
        self.assertEqual(n.level, 'info')
        self.assertEqual(n.verb, 'default verb')
        self.assertIn(
            'Default notification with default verb and level info', n.message
        )

    def test_object_metric_multiple_notifications(self):
        testorg = self._create_org()
        admin = self._create_admin()
        staff = self._create_user(
            username='staff', email='staff@staff.com', password='staff', is_staff=True
        )
        self._create_user(
            username='staff-lone',
            email='staff-lone@staff.com',
            password='staff',
            is_staff=True,
        )
        user = self._create_user(is_staff=False)
        OrganizationUser.objects.create(user=user, organization=testorg)
        OrganizationUser.objects.create(user=staff, organization=testorg)
        self.assertIsNotNone(staff.notificationuser)
        d = self._create_device(organization=testorg)
        om = self._create_object_metric(name='load', content_object=d)
        alert_s = self._create_alert_settings(metric=om, operator='>', value=90, seconds=61)
        om._notify_users(notification_type='default', alert_settings=alert_s)
        self.assertEqual(Notification.objects.count(), 2)
        n = notification_queryset.first()
        self.assertEqual(n.recipient, admin)
        self.assertEqual(n.actor, om)
        self.assertEqual(n.target, d)
        self.assertEqual(n.action_object, om.alertsettings)
        self.assertEqual(n.level, 'info')
        self.assertEqual(n.verb, 'default verb')
        self.assertIn(
            'Default notification with default verb and level info', n.message,
        )
        n = notification_queryset.last()
        self.assertEqual(n.recipient, staff)
        self.assertEqual(n.actor, om)
        self.assertEqual(n.target, d)
        self.assertEqual(n.action_object, om.alertsettings)
        self.assertEqual(n.level, 'info')
        self.assertEqual(n.verb, 'default verb')

    def test_object_metric_multiple_notifications_no_org(self):
        testorg = self._create_org()
        admin = self._create_admin()
        staff = self._create_user(
            username='staff', email='staff@staff.com', password='staff', is_staff=True
        )
        self._create_user(
            username='staff-lone',
            email='staff-lone@staff.com',
            password='staff',
            is_staff=True,
            first_name="'staff-lone'",
        )
        user = self._create_user(is_staff=False)
        OrganizationUser.objects.create(user=user, organization=testorg)
        OrganizationUser.objects.create(user=staff, organization=testorg)
        self.assertIsNotNone(staff.notificationuser)
        om = self._create_object_metric(name='logins', content_object=user)
        alert_s = self._create_alert_settings(metric=om, operator='>', value=90, seconds=0)
        om._notify_users(notification_type='default', alert_settings=alert_s)
        self.assertEqual(Notification.objects.count(), 1)
        n = notification_queryset.first()
        self.assertEqual(n.recipient, admin)
        self.assertEqual(n.actor, om)
        self.assertEqual(n.target, user)
        self.assertEqual(n.action_object, om.alertsettings)
        self.assertEqual(n.level, 'info')
        self.assertEqual(n.verb, 'default verb')

    def test_email_notification(self):
        self._create_admin()
        d = self._create_device(organization=self._get_org())
        m = self._create_general_metric(name='load', content_object=d)
        self._create_alert_settings(metric=m, operator='>', value=90, seconds=0)
        exp_target_link = f'http://example.com/admin/config/device/{d.id}/change/'
        exp_email_body = '{message}' f'\n\nFor more information see {exp_target_link}.'

        with self.subTest("Test notification email for metric crossed alert settings"):
            m.write(99)
            n = notification_queryset.first()
            email = mail.outbox.pop()
            html_message, content_type = email.alternatives.pop()
            self.assertEqual(email.subject, n.email_subject)
            self.assertEqual(
                email.body, exp_email_body.format(message=strip_tags(n.message))
            )
            self.assertIn(n.message, html_message)
            self.assertIn(
                f'<a href="{exp_target_link}">'
                'For further information see "device: test-device".</a>',
                html_message,
            )

        with self.subTest("Test notification email for metric returned under threhold"):
            m.write(50)
            n = notification_queryset.last()
            email = mail.outbox.pop()
            html_message, content_type = email.alternatives.pop()
            self.assertEqual(email.subject, n.email_subject)
            self.assertEqual(
                email.body, exp_email_body.format(message=strip_tags(n.message))
            )
            self.assertIn(n.message, html_message)
            self.assertIn(
                f'<a href="{exp_target_link}">'
                'For further information see "device: test-device".</a>',
                html_message,
            )

    def test_notification_types(self):
        self._create_admin()
        m = self._create_object_metric(name='load')
        self._create_alert_settings(metric=m, operator='>', value=90, seconds=0)
        exp_message = (
            '<p>{n.actor.name} for device '
            '"<a href="http://example.com/admin/openwisp_users/user/{n.target.id}/change/">tester</a>"'
            ' {n.verb}.</p>'
        )
        with self.subTest("Test notification for 'alert settings crossed'"):
            m.write(99)
            n = notification_queryset.first()
            self.assertEqual(n.level, 'warning')
            self.assertEqual(n.verb, 'crossed alert settings limit')
            self.assertEqual(
                n.email_subject, f'[example.com] PROBLEM: {n.actor.name} {n.target}',
            )
            self.assertEqual(n.message, exp_message.format(n=n))

        with self.subTest("Test notification for 'under alert settings'"):
            m.write(80)
            n = notification_queryset.last()
            self.assertEqual(n.level, 'info')
            self.assertEqual(n.verb, 'returned within alert settings limit')
            self.assertEqual(
                n.email_subject, f'[example.com] RECOVERY: {n.actor.name} {n.target}',
            )
            self.assertEqual(n.message, exp_message.format(n=n))
