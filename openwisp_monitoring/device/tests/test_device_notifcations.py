from django.core import mail
from django.utils.html import strip_tags
from swapper import load_model

from openwisp_controller.connection.models import Credentials, DeviceConnection

from .test_models import BaseTestCase

Notification = load_model('openwisp_notifications', 'Notification')


class TestDeviceNotifications(BaseTestCase):
    def setUp(self):
        self._create_admin()
        self.d = self._create_device()
        self.creds = Credentials.objects.create(
            connector='openwisp_controller.connection.connectors.ssh.Ssh'
        )
        self.dc = DeviceConnection.objects.create(credentials=self.creds, device=self.d)

    def _generic_notification_test(
        self, exp_level, exp_type, exp_verb, exp_message, exp_email_subject
    ):
        exp_target_link = f'http://example.com/admin/config/device/{self.d.id}/change/'
        exp_email_body = '{message}' f'\n\nFor more information see {exp_target_link}.'

        n = Notification.objects.first()
        email = mail.outbox.pop()
        html_message, content_type = email.alternatives.pop()
        self.assertEqual(n.type, exp_type)
        self.assertEqual(n.level, exp_level)
        self.assertEqual(n.verb, exp_verb)
        self.assertEqual(n.actor, self.dc)
        self.assertEqual(n.target, self.d)
        self.assertEqual(
            n.message, exp_message.format(n=n, target_link=exp_target_link)
        )
        self.assertEqual(
            n.email_subject, exp_email_subject.format(n=n),
        )
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

    def test_connection_working_notification(self):
        self.dc = DeviceConnection.objects.create(
            credentials=self.creds, device=self.d, is_working=False
        )
        self.dc.is_working = True
        self.dc.save()
        self._generic_notification_test(
            exp_level='info',
            exp_type='connection_is_working',
            exp_verb='working',
            exp_message=(
                '<p>(SSH) connection to <a href="{target_link}">'
                'Device: {n.target}</a> is {n.verb}. </p>'
            ),
            exp_email_subject='[example.com] RECOVERY: Device "{n.target}"',
        )

    def test_connection_not_working_notification(self):
        self.dc.is_working = False
        self.dc.save()
        self._generic_notification_test(
            exp_level='error',
            exp_type='connection_is_not_working',
            exp_verb='not working',
            exp_message=(
                '<p>(SSH) connection to <a href="{target_link}">'
                'Device: {n.target}</a> is {n.verb}. </p>'
            ),
            exp_email_subject='[example.com] PROBLEM: Device "{n.target}"',
        )

    def test_unreachable_after_upgrade_notification(self):
        self.dc.is_working = False
        self.dc.failure_reason = 'Giving up, device not reachable anymore after upgrade'
        self.dc.save()
        self._generic_notification_test(
            exp_level='error',
            exp_type='connection_is_not_working',
            exp_verb='not working',
            exp_message=(
                '<p>(SSH) connection to <a href="{target_link}">'
                'Device: {n.target}</a> is {n.verb}.'
                ' Giving up, device not reachable anymore after upgrade</p>'
            ),
            exp_email_subject='[example.com] PROBLEM: Device "{n.target}"',
        )
