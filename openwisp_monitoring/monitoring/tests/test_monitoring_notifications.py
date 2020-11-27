from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from django.urls import reverse
from django.utils import timezone
from django.utils.html import strip_tags
from freezegun import freeze_time
from swapper import load_model

from ...device.tests import DeviceMonitoringTestCase

Metric = load_model('monitoring', 'Metric')
Notification = load_model('openwisp_notifications', 'Notification')
Device = load_model('config', 'Device')
Config = load_model('config', 'Config')
OrganizationUser = load_model('openwisp_users', 'OrganizationUser')

notification_queryset = Notification.objects.order_by('timestamp')
start_time = timezone.now()
ten_minutes_ago = start_time - timedelta(minutes=10)
ten_minutes_after = start_time + timedelta(minutes=10)


class TestMonitoringNotifications(DeviceMonitoringTestCase):
    device_model = Device
    config_model = Config

    def test_general_check_threshold_crossed_immediate(self):
        admin = self._create_admin()
        m = self._create_general_metric(name='load')
        self._create_alert_settings(
            metric=m, custom_operator='>', custom_threshold=90, custom_tolerance=0
        )

        with self.subTest('Test notification for metric exceeding alert settings'):
            m.write(99)
            m.refresh_from_db()
            self.assertFalse(m.is_healthy)
            self.assertEqual(Notification.objects.count(), 1)
            n = notification_queryset.first()
            self.assertEqual(n.recipient, admin)
            self.assertEqual(n.actor, m)
            self.assertEqual(n.action_object, m.alertsettings)
            self.assertEqual(n.level, 'warning')

        with self.subTest('Test no double alarm for metric exceeding alert settings'):
            m.write(95)
            m.refresh_from_db()
            self.assertFalse(m.is_healthy)
            self.assertEqual(Notification.objects.count(), 1)

        with self.subTest('Test notification for metric falling behind alert settings'):
            m.write(60)
            m.refresh_from_db()
            self.assertTrue(m.is_healthy)
            self.assertEqual(Notification.objects.count(), 2)
            n = notification_queryset.last()
            self.assertEqual(n.recipient, admin)
            self.assertEqual(n.actor, m)
            self.assertEqual(n.action_object, m.alertsettings)
            self.assertEqual(n.level, 'info')

        with self.subTest(
            'Test no double alarm for metric falling behind alert settings'
        ):
            m.write(40)
            m.refresh_from_db()
            self.assertTrue(m.is_healthy)
            self.assertEqual(Notification.objects.count(), 2)

    def test_general_check_threshold_crossed_deferred(self):
        admin = self._create_admin()
        m = self._create_general_metric(name='load')
        self._create_alert_settings(
            metric=m, custom_operator='>', custom_threshold=90, custom_tolerance=1
        )
        m.write(99, time=ten_minutes_ago)
        m.refresh_from_db()
        self.assertFalse(m.is_healthy)
        self.assertEqual(Notification.objects.count(), 1)
        n = notification_queryset.first()
        self.assertEqual(n.recipient, admin)
        self.assertEqual(n.actor, m)
        self.assertEqual(n.action_object, m.alertsettings)
        self.assertEqual(n.level, 'warning')

    def test_general_check_threshold_deferred_not_crossed(self):
        self._create_admin()
        m = self._create_general_metric(name='load')
        self._create_alert_settings(
            metric=m, custom_operator='>', custom_threshold=90, custom_tolerance=1
        )
        m.write(99)
        self.assertTrue(m.is_healthy)
        self.assertEqual(Notification.objects.count(), 0)

    def test_resources_metric_threshold_deferred_not_crossed(self):
        # Verify that newly created metrics within threshold limit don't send any notifications
        self._create_admin()
        self.create_test_data()
        self.assertEqual(Notification.objects.count(), 0)

    def test_cpu_metric_threshold_crossed(self):
        admin = self._create_admin()
        test_data_path = (
            'openwisp_monitoring.device.tests.DeviceMonitoringTestCase._data'
        )
        data = self._data()
        data['resources']['load'] = [0.99, 0.99, 0.99]
        with patch(test_data_path, return_value=data):
            self.create_test_data()
            m = Metric.objects.get(name='CPU usage')
            self.assertEqual(Notification.objects.count(), 1)
            n = Notification.objects.first()
            self.assertEqual(n.recipient, admin)
            self.assertEqual(n.actor, m)
            self.assertEqual(n.action_object, m.alertsettings)
            self.assertEqual(n.level, 'warning')

    def test_general_check_threshold_crossed_for_long_time(self):
        """
        this is going to be the most realistic scenario:
        incoming metrics will always be stored with the current
        timestamp, which means the system must be able to look
        back in previous measurements to see if the AlertSettings
        has been crossed for long enough
        """
        admin = self._create_admin()
        m = self._create_general_metric(name='load')
        self._create_alert_settings(
            metric=m, custom_operator='>', custom_threshold=90, custom_tolerance=5
        )

        with self.subTest('Test no notification is generated for healthy status'):
            m.write(89, time=ten_minutes_ago)
            m.refresh_from_db()
            self.assertTrue(m.is_healthy)
            self.assertEqual(Notification.objects.count(), 0)

        with self.subTest('Test no notification is generated when check=False'):
            m.write(91, time=ten_minutes_ago, check=False)
            self.assertEqual(Notification.objects.count(), 0)

        with self.subTest('Test notification for metric with current timestamp'):
            m.write(92)
            m.refresh_from_db()
            self.assertFalse(m.is_healthy)
            self.assertEqual(Notification.objects.count(), 1)
            n = notification_queryset.first()
            self.assertEqual(n.recipient, admin)
            self.assertEqual(n.actor, m)
            self.assertEqual(n.action_object, m.alertsettings)
            self.assertEqual(n.level, 'warning')

        with self.subTest('Test no recovery notification yet (tolerance not passed)'):
            m.write(50)
            m.refresh_from_db()
            self.assertFalse(m.is_healthy)
            self.assertEqual(Notification.objects.count(), 1)

        with self.subTest('Tolerance still not passed, not expecting a recovery yet'):
            with freeze_time(start_time + timedelta(minutes=2)):
                m.write(51)
            m.refresh_from_db()
            self.assertFalse(m.is_healthy)
            self.assertEqual(Notification.objects.count(), 1)

        with self.subTest('Test recovery notification after tolerance is passed'):
            with freeze_time(ten_minutes_after):
                m.write(50)
            m.refresh_from_db()
            self.assertTrue(m.is_healthy)
            self.assertEqual(Notification.objects.count(), 2)
            n = notification_queryset.last()
            self.assertEqual(n.recipient, admin)
            self.assertEqual(n.actor, m)
            self.assertEqual(n.action_object, m.alertsettings)
            self.assertEqual(n.level, 'info')

    def test_object_check_threshold_crossed_immediate(self):
        admin = self._create_admin()
        om = self._create_object_metric(name='load')
        alert_s = self._create_alert_settings(
            metric=om, custom_operator='>', custom_threshold=90, custom_tolerance=0
        )

        with self.subTest(
            "Test notification for object metric exceeding alert settings"
        ):
            om.write(99)
            om.refresh_from_db()
            self.assertFalse(om.is_healthy)
            self.assertEqual(Notification.objects.count(), 1)
            n = notification_queryset.first()
            self.assertEqual(n.recipient, admin)
            self.assertEqual(n.actor, om)
            self.assertEqual(n.action_object, alert_s)
            self.assertEqual(n.target, om.content_object)
            self.assertEqual(n.level, 'warning')

        with self.subTest(
            "Test no double alarm for object metric exceeding alert settings"
        ):
            om.write(95)
            om.refresh_from_db()
            self.assertFalse(om.is_healthy)
            self.assertEqual(Notification.objects.count(), 1)

        with self.subTest(
            "Test notification for object metric falling behind alert settings"
        ):
            om.write(60)
            om.refresh_from_db()
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
            om.refresh_from_db()
            self.assertTrue(om.is_healthy)
            self.assertEqual(Notification.objects.count(), 2)

    def test_object_check_threshold_crossed_deferred(self):
        admin = self._create_admin()
        om = self._create_object_metric(name='load')
        alert_s = self._create_alert_settings(
            metric=om, custom_operator='>', custom_threshold=90, custom_tolerance=1
        )
        om.write(99, time=ten_minutes_ago)
        om.refresh_from_db()
        self.assertFalse(om.is_healthy)
        self.assertEqual(Notification.objects.count(), 1)
        n = notification_queryset.first()
        self.assertEqual(n.recipient, admin)
        self.assertEqual(n.actor, om)
        self.assertEqual(n.action_object, alert_s)
        self.assertEqual(n.target, om.content_object)
        self.assertEqual(n.level, 'warning')

    def test_object_check_threshold_deferred_not_crossed(self):
        self._create_admin()
        om = self._create_object_metric(name='load')
        self._create_alert_settings(
            metric=om, custom_operator='>', custom_threshold=90, custom_tolerance=1
        )
        om.write(99)
        om.refresh_from_db()
        self.assertTrue(om.is_healthy)
        self.assertEqual(Notification.objects.count(), 0)

    def test_object_check_threshold_crossed_for_long_time(self):
        admin = self._create_admin()
        om = self._create_object_metric(name='load')
        alert_s = self._create_alert_settings(
            metric=om, custom_operator='>', custom_threshold=90, custom_tolerance=1
        )
        om.write(89, time=ten_minutes_ago)
        self.assertEqual(Notification.objects.count(), 0)
        om.write(91, time=ten_minutes_ago, check=False)
        self.assertEqual(Notification.objects.count(), 0)
        om.write(92)
        om.refresh_from_db()
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
        om.refresh_from_db()
        self.assertFalse(om.is_healthy)
        self.assertEqual(Notification.objects.count(), 1)
        # value back to normal but tolerance not passed yet
        om.write(60)
        om.refresh_from_db()
        self.assertFalse(om.is_healthy)
        self.assertEqual(Notification.objects.count(), 1)
        # tolerance passed
        with freeze_time(ten_minutes_after):
            om.write(60)
        om.refresh_from_db()
        self.assertTrue(om.is_healthy)
        self.assertEqual(Notification.objects.count(), 2)
        n = notification_queryset.last()
        self.assertEqual(n.recipient, admin)
        self.assertEqual(n.actor, om)
        self.assertEqual(n.action_object, alert_s)
        self.assertEqual(n.target, om.content_object)
        self.assertEqual(n.level, 'info')
        # ensure double alarm not sent
        with freeze_time(ten_minutes_after + timedelta(minutes=5)):
            om.write(40)
        om.refresh_from_db()
        self.assertTrue(om.is_healthy)
        self.assertEqual(Notification.objects.count(), 2)

    def test_flapping_metric_with_tolerance(self):
        self._create_admin()
        om = self._create_object_metric(name='ping')
        self._create_alert_settings(
            metric=om, custom_operator='<', custom_threshold=1, custom_tolerance=10
        )
        with freeze_time(start_time - timedelta(minutes=25)):
            om.write(1)
            self.assertEqual(Notification.objects.count(), 0)
            om.refresh_from_db()
            self.assertTrue(om.is_healthy)
        with freeze_time(start_time - timedelta(minutes=20)):
            om.write(0)
            self.assertEqual(Notification.objects.count(), 0)
            om.refresh_from_db()
            self.assertTrue(om.is_healthy)
        with freeze_time(start_time - timedelta(minutes=15)):
            om.write(1)
            self.assertEqual(Notification.objects.count(), 0)
            om.refresh_from_db()
            self.assertTrue(om.is_healthy)
        with freeze_time(start_time - timedelta(minutes=10)):
            om.write(0)
            self.assertEqual(Notification.objects.count(), 0)
            om.refresh_from_db()
            self.assertTrue(om.is_healthy)
        with freeze_time(start_time - timedelta(minutes=5)):
            om.write(0)
            self.assertEqual(Notification.objects.count(), 0)
            om.refresh_from_db()
            self.assertTrue(om.is_healthy)
        om.write(0)
        self.assertEqual(Notification.objects.count(), 1)
        om.refresh_from_db()
        self.assertFalse(om.is_healthy)

    def test_multiple_notifications(self):
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
        OrganizationUser.objects.create(user=user, organization=testorg, is_admin=True)
        OrganizationUser.objects.create(user=staff, organization=testorg, is_admin=True)
        self.assertIsNotNone(staff.notificationsetting_set.filter(organization=testorg))

        with self.subTest('Test general metric multiple notifications'):
            m = self._create_general_metric(name='load')
            alert_s = self._create_alert_settings(
                metric=m, custom_operator='>', custom_threshold=90, custom_tolerance=1
            )
            m._notify_users(notification_type='ping_problem', alert_settings=alert_s)
            self.assertEqual(Notification.objects.count(), 1)
            n = notification_queryset.first()
            self._check_notification_parameters(n, admin, m, None)
            self.assertEqual(
                '<p>The device <a href="#">None</a> is not reachable.</p>', n.message
            )
            Notification.objects.all().delete()

        with self.subTest('Test object metric multiple notifications'):
            d = self._create_device(organization=testorg)
            om = self._create_object_metric(name='load', content_object=d)
            alert_s = self._create_alert_settings(
                metric=om, custom_operator='>', custom_threshold=90, custom_tolerance=1
            )
            self.assertEqual(Notification.objects.count(), 0)
            om._notify_users(notification_type='ping_problem', alert_settings=alert_s)
            self.assertEqual(Notification.objects.count(), 2)
            n = notification_queryset.first()
            self._check_notification_parameters(n, admin, om, d)
            self.assertIn('is not reachable.', n.message)
            n = notification_queryset.last()
            self._check_notification_parameters(n, staff, om, d)
            Notification.objects.all().delete()

        with self.subTest('Test object metric multiple notifications no org'):
            om = self._create_object_metric(name='logins', content_object=user)
            alert_s = self._create_alert_settings(
                metric=om, custom_operator='>', custom_threshold=90, custom_tolerance=0
            )
            self.assertEqual(Notification.objects.count(), 0)
            om._notify_users(notification_type='ping_problem', alert_settings=alert_s)
            self.assertEqual(Notification.objects.count(), 1)
            n = notification_queryset.first()
            self._check_notification_parameters(n, admin, om, user)

    def _check_notification_parameters(self, notification, recepient, metric, target):
        self.assertEqual(notification.recipient, recepient)
        self.assertEqual(notification.actor, metric)
        self.assertEqual(notification.target, target)
        self.assertEqual(notification.action_object, metric.alertsettings)
        self.assertEqual(notification.level, 'warning')
        self.assertEqual(notification.verb, 'is not reachable')

    def test_email_notification(self):
        self._create_admin()
        d = self._create_device(organization=self._get_org())
        m = self._create_general_metric(name='load', content_object=d)
        self._create_alert_settings(
            metric=m, custom_operator='>', custom_threshold=90, custom_tolerance=0
        )
        exp_target_link = f'https://example.com/admin/config/device/{d.id}/change/'
        exp_email_body = '{message}\n\nFor more information see {email_link}.'

        with self.subTest('Test notification email for metric crossed alert settings'):
            m.write(99)
            n = notification_queryset.first()
            url_path = reverse('notifications:notification_read_redirect', args=[n.pk])
            email_link = f'https://example.com{url_path}'
            email = mail.outbox.pop()
            html_message, content_type = email.alternatives.pop()
            self.assertEqual(email.subject, n.email_subject)
            self.assertEqual(
                email.body,
                exp_email_body.format(
                    message=strip_tags(n.message), email_link=email_link
                ),
            )
            self.assertIn(
                f'<a href="{email_link}">'
                'For further information see "device: default.test.device".</a>',
                html_message,
            )
            self.assertIn(exp_target_link, n.message)

        with self.subTest('Test notification email for metric returned under threhold'):
            m.write(50)
            n = notification_queryset.last()
            url_path = reverse('notifications:notification_read_redirect', args=[n.pk])
            email_link = f'https://example.com{url_path}'
            email = mail.outbox.pop()
            html_message, content_type = email.alternatives.pop()
            self.assertEqual(email.subject, n.email_subject)
            self.assertEqual(
                email.body,
                exp_email_body.format(
                    message=strip_tags(n.message), email_link=email_link
                ),
            )
            self.assertIn(
                f'<a href="{email_link}">'
                'For further information see "device: default.test.device".</a>',
                html_message,
            )
            self.assertIn(exp_target_link, n.message)

    def test_notification_types(self):
        self._create_admin()
        m = self._create_object_metric(name='load')
        self._create_alert_settings(
            metric=m, custom_operator='>', custom_threshold=90, custom_tolerance=0
        )
        exp_message = (
            '<p>{n.actor.name} for device '
            '<a href="https://example.com/admin/openwisp_users/user/{n.target.id}/change/">tester</a>'
            ' {n.verb}.</p>'
        )
        with self.subTest("Test notification for 'alert settings crossed'"):
            m.write(99)
            n = notification_queryset.first()
            self.assertEqual(n.level, 'warning')
            self.assertEqual(n.verb, 'crossed the threshold')
            self.assertEqual(
                n.email_subject, f'[example.com] PROBLEM: {n.actor.name} {n.target}'
            )
            self.assertEqual(n.message, exp_message.format(n=n))

        with self.subTest("Test notification for 'under alert settings'"):
            m.write(80)
            n = notification_queryset.last()
            self.assertEqual(n.level, 'info')
            self.assertEqual(n.verb, 'returned within the threshold')
            self.assertEqual(
                n.email_subject, f'[example.com] RECOVERY: {n.actor.name} {n.target}'
            )
            self.assertEqual(n.message, exp_message.format(n=n))

    def test_alerts_disabled(self):
        self._create_admin()
        d = self._create_device(organization=self._get_org())
        m = self._create_general_metric(name='load', content_object=d)
        self._create_alert_settings(
            metric=m,
            custom_operator='>',
            custom_threshold=90,
            custom_tolerance=1,
            is_active=False,
        )
        m.write(99, time=ten_minutes_ago)
        m.refresh_from_db()
        self.assertFalse(m.is_healthy)
        d.refresh_from_db()
        self.assertEqual(d.monitoring.status, 'problem')
        self.assertEqual(Notification.objects.count(), 0)
