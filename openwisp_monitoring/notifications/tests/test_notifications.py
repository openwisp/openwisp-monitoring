from datetime import timedelta

from django.core import mail
from django.test import TestCase
from django.utils import timezone
from swapper import load_model

from openwisp_controller.config.models import Config, Device
from openwisp_controller.config.tests import CreateConfigTemplateMixin
from openwisp_users.models import OrganizationUser

from ...monitoring.tests import TestMonitoringMixin

Notification = Notification = load_model('notifications', 'Notification')
notification_queryset = Notification.objects.order_by('timestamp')
start_time = timezone.now()
ten_minutes_ago = start_time - timedelta(minutes=10)


class TestNotifications(CreateConfigTemplateMixin, TestMonitoringMixin, TestCase):
    device_model = Device
    config_model = Config

    def test_general_check_threshold_crossed_immediate(self):
        admin = self._create_admin()
        m = self._create_general_metric(name='load')
        self._create_threshold(metric=m,
                               operator='>',
                               value=90,
                               seconds=0)
        m.write(99)
        self.assertFalse(m.is_healthy)
        self.assertEqual(Notification.objects.count(), 1)
        n = notification_queryset.first()
        self.assertEqual(n.recipient, admin)
        self.assertEqual(n.actor, m)
        self.assertEqual(n.action_object, m.threshold)
        self.assertEqual(n.level, 'warning')
        # ensure double alarm not sent
        m.write(95)
        self.assertFalse(m.is_healthy)
        self.assertEqual(Notification.objects.count(), 1)
        # threshold back to normal
        m.write(60)
        self.assertTrue(m.is_healthy)
        self.assertEqual(Notification.objects.count(), 2)
        n = notification_queryset.last()
        self.assertEqual(n.recipient, admin)
        self.assertEqual(n.actor, m)
        self.assertEqual(n.action_object, m.threshold)
        self.assertEqual(n.level, 'info')
        # ensure double alarm not sent
        m.write(40)
        self.assertTrue(m.is_healthy)
        self.assertEqual(Notification.objects.count(), 2)

    def test_general_check_threshold_crossed_deferred(self):
        admin = self._create_admin()
        m = self._create_general_metric(name='load')
        self._create_threshold(metric=m,
                               operator='>',
                               value=90,
                               seconds=60)
        m.write(99, time=ten_minutes_ago)
        self.assertFalse(m.is_healthy)
        self.assertEqual(Notification.objects.count(), 1)
        n = notification_queryset.first()
        self.assertEqual(n.recipient, admin)
        self.assertEqual(n.actor, m)
        self.assertEqual(n.action_object, m.threshold)
        self.assertEqual(n.level, 'warning')

    def test_general_check_threshold_deferred_not_crossed(self):
        self._create_admin()
        m = self._create_general_metric(name='load')
        self._create_threshold(metric=m,
                               operator='>',
                               value=90,
                               seconds=60)
        m.write(99)
        self.assertTrue(m.is_healthy)
        self.assertEqual(Notification.objects.count(), 0)

    def test_general_check_threshold_crossed_for_long_time(self):
        """
        this is going to be the most realistic scenario:
        incoming metrics will always be stored with the current
        timestamp, which means the system must be able to look
        back in previous measurements to see if the threshold
        has been crossed for long enough
        """
        admin = self._create_admin()
        m = self._create_general_metric(name='load')
        self._create_threshold(metric=m,
                               operator='>',
                               value=90,
                               seconds=61)
        m.write(89, time=ten_minutes_ago)
        self.assertTrue(m.is_healthy)
        self.assertEqual(Notification.objects.count(), 0)
        # this write won't trigger a notification
        m.write(91, time=ten_minutes_ago,
                check=False)
        self.assertEqual(Notification.objects.count(), 0)
        # this one will
        m.write(92)
        self.assertFalse(m.is_healthy)
        self.assertEqual(Notification.objects.count(), 1)
        n = notification_queryset.first()
        self.assertEqual(n.recipient, admin)
        self.assertEqual(n.actor, m)
        self.assertEqual(n.action_object, m.threshold)
        self.assertEqual(n.level, 'warning')
        # ensure double alarm not sent
        m.write(95)
        self.assertFalse(m.is_healthy)
        self.assertEqual(Notification.objects.count(), 1)
        # threshold back to normal
        m.write(60)
        self.assertTrue(m.is_healthy)
        self.assertEqual(Notification.objects.count(), 2)
        n = notification_queryset.last()
        self.assertEqual(n.recipient, admin)
        self.assertEqual(n.actor, m)
        self.assertEqual(n.action_object, m.threshold)
        self.assertEqual(n.level, 'info')
        # ensure double alarm not sent
        m.write(40)
        self.assertTrue(m.is_healthy)
        self.assertEqual(Notification.objects.count(), 2)

    def test_object_check_threshold_crossed_immediate(self):
        admin = self._create_admin()
        om = self._create_object_metric(name='load')
        t = self._create_threshold(metric=om,
                                   operator='>',
                                   value=90,
                                   seconds=0)
        om.write(99)
        self.assertFalse(om.is_healthy)
        self.assertEqual(Notification.objects.count(), 1)
        n = notification_queryset.first()
        self.assertEqual(n.recipient, admin)
        self.assertEqual(n.actor, om)
        self.assertEqual(n.action_object, t)
        self.assertEqual(n.target, om.content_object)
        self.assertEqual(n.level, 'warning')
        # ensure double alarm not sent
        om.write(95)
        self.assertFalse(om.is_healthy)
        self.assertEqual(Notification.objects.count(), 1)
        # threshold back to normal
        om.write(60)
        self.assertTrue(om.is_healthy)
        self.assertEqual(Notification.objects.count(), 2)
        n = notification_queryset.last()
        self.assertEqual(n.recipient, admin)
        self.assertEqual(n.actor, om)
        self.assertEqual(n.action_object, t)
        self.assertEqual(n.target, om.content_object)
        self.assertEqual(n.level, 'info')
        # ensure double alarm not sent
        om.write(40)
        self.assertTrue(om.is_healthy)
        self.assertEqual(Notification.objects.count(), 2)

    def test_object_check_threshold_crossed_deferred(self):
        admin = self._create_admin()
        om = self._create_object_metric(name='load')
        t = self._create_threshold(metric=om,
                                   operator='>',
                                   value=90,
                                   seconds=60)
        om.write(99, time=ten_minutes_ago)
        self.assertFalse(om.is_healthy)
        self.assertEqual(Notification.objects.count(), 1)
        n = notification_queryset.first()
        self.assertEqual(n.recipient, admin)
        self.assertEqual(n.actor, om)
        self.assertEqual(n.action_object, t)
        self.assertEqual(n.target, om.content_object)
        self.assertEqual(n.level, 'warning')

    def test_object_check_threshold_deferred_not_crossed(self):
        self._create_admin()
        om = self._create_object_metric(name='load')
        self._create_threshold(metric=om,
                               operator='>',
                               value=90,
                               seconds=60)
        om.write(99)
        self.assertTrue(om.is_healthy)
        self.assertEqual(Notification.objects.count(), 0)

    def test_object_check_threshold_crossed_for_long_time(self):
        admin = self._create_admin()
        om = self._create_object_metric(name='load')
        t = self._create_threshold(metric=om,
                                   operator='>',
                                   value=90,
                                   seconds=61)
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
        self.assertEqual(n.action_object, t)
        self.assertEqual(n.target, om.content_object)
        self.assertEqual(n.level, 'warning')
        # ensure double alarm not sent
        om.write(95)
        self.assertFalse(om.is_healthy)
        self.assertEqual(Notification.objects.count(), 1)
        # threshold back to normal
        om.write(60)
        self.assertTrue(om.is_healthy)
        self.assertEqual(Notification.objects.count(), 2)
        n = notification_queryset.last()
        self.assertEqual(n.recipient, admin)
        self.assertEqual(n.actor, om)
        self.assertEqual(n.action_object, t)
        self.assertEqual(n.target, om.content_object)
        self.assertEqual(n.level, 'info')
        # ensure double alarm not sent
        om.write(40)
        self.assertTrue(om.is_healthy)
        self.assertEqual(Notification.objects.count(), 2)

    def test_general_metric_multiple_notifications(self):
        testorg = self._create_org()
        admin = self._create_admin()
        staff = self._create_user(username='staff',
                                  email='staff@staff.com',
                                  password='staff',
                                  is_staff=True)
        self._create_user(username='staff-lone',
                          email='staff-lone@staff.com',
                          password='staff',
                          is_staff=True)
        user = self._create_user(is_staff=False)
        OrganizationUser.objects.create(user=user, organization=testorg)
        OrganizationUser.objects.create(user=staff, organization=testorg)
        self.assertIsNotNone(staff.notificationuser)
        m = self._create_general_metric(name='load')
        t = self._create_threshold(metric=m,
                                   operator='>',
                                   value=90,
                                   seconds=61)
        m._notify_users(level='info', verb='test', threshold=t)
        self.assertEqual(Notification.objects.count(), 1)
        n = notification_queryset.first()
        self.assertEqual(n.recipient, admin)
        self.assertEqual(n.actor, m)
        self.assertEqual(n.target, None)
        self.assertEqual(n.action_object, m.threshold)
        self.assertEqual(n.level, 'info')
        self.assertEqual(n.verb, 'test')
        self.assertIsNotNone(n.description)
        self.assertNotEqual(n.description, '')

    def test_object_metric_multiple_notifications(self):
        testorg = self._create_org()
        admin = self._create_admin()
        staff = self._create_user(username='staff',
                                  email='staff@staff.com',
                                  password='staff',
                                  is_staff=True)
        self._create_user(username='staff-lone',
                          email='staff-lone@staff.com',
                          password='staff',
                          is_staff=True)
        user = self._create_user(is_staff=False)
        OrganizationUser.objects.create(user=user, organization=testorg)
        OrganizationUser.objects.create(user=staff, organization=testorg)
        self.assertIsNotNone(staff.notificationuser)
        d = self._create_device(organization=testorg)
        om = self._create_object_metric(name='load', content_object=d)
        t = self._create_threshold(metric=om,
                                   operator='>',
                                   value=90,
                                   seconds=61)
        om._notify_users(level='info', verb='test', threshold=t)
        self.assertEqual(Notification.objects.count(), 2)
        n = notification_queryset.first()
        self.assertEqual(n.recipient, admin)
        self.assertEqual(n.actor, om)
        self.assertEqual(n.target, d)
        self.assertEqual(n.action_object, om.threshold)
        self.assertEqual(n.level, 'info')
        self.assertEqual(n.verb, 'test')
        self.assertIsNotNone(n.description)
        self.assertNotEqual(n.description, '')
        n = notification_queryset.last()
        self.assertEqual(n.recipient, staff)
        self.assertEqual(n.actor, om)
        self.assertEqual(n.target, d)
        self.assertEqual(n.action_object, om.threshold)
        self.assertEqual(n.level, 'info')
        self.assertEqual(n.verb, 'test')

    def test_object_metric_multiple_notifications_no_org(self):
        testorg = self._create_org()
        admin = self._create_admin()
        staff = self._create_user(username='staff',
                                  email='staff@staff.com',
                                  password='staff',
                                  is_staff=True)
        self._create_user(username='staff-lone',
                          email='staff-lone@staff.com',
                          password='staff',
                          is_staff=True)
        user = self._create_user(is_staff=False)
        OrganizationUser.objects.create(user=user, organization=testorg)
        OrganizationUser.objects.create(user=staff, organization=testorg)
        self.assertIsNotNone(staff.notificationuser)
        om = self._create_object_metric(name='logins', content_object=user)
        t = self._create_threshold(metric=om,
                                   operator='>',
                                   value=90,
                                   seconds=0)
        om._notify_users(level='info', verb='test', threshold=t)
        self.assertEqual(Notification.objects.count(), 1)
        n = notification_queryset.first()
        self.assertEqual(n.recipient, admin)
        self.assertEqual(n.actor, om)
        self.assertEqual(n.target, user)
        self.assertEqual(n.action_object, om.threshold)
        self.assertEqual(n.level, 'info')
        self.assertEqual(n.verb, 'test')

    def _create_notification(self):
        d = self._create_device(organization=self._create_org())
        m = self._create_object_metric(name='load', content_object=d)
        self._create_threshold(metric=m,
                               operator='>',
                               value=90,
                               seconds=0)
        m.write(99)

    def test_superuser_notifications_disabled(self):
        admin = self._create_admin()
        self.assertEqual(admin.notificationuser.email, True)
        admin.notificationuser.receive = False
        admin.notificationuser.save()
        self._create_notification()
        self.assertEqual(admin.notificationuser.email, False)
        self.assertEqual(Notification.objects.count(), 0)

    def test_email_sent(self):
        admin = self._create_admin()
        self._create_notification()
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [admin.email])
        n = Notification.objects.first()
        self.assertEqual(mail.outbox[0].subject, n.data.get('email_subject'))
        self.assertIn(n.description, mail.outbox[0].body)
        self.assertIn(n.data.get('url'), mail.outbox[0].body)
        self.assertIn('https://', n.data.get('url'))

    def test_email_disabled(self):
        admin = self._create_admin()
        admin.notificationuser.email = False
        admin.notificationuser.save()
        self._create_notification()
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_email_not_present(self):
        admin = self._create_admin()
        admin.email = ''
        admin.save()
        self._create_notification()
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 0)
