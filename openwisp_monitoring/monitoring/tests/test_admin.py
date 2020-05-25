from django.test import TestCase
from django.urls import reverse
from swapper import load_model

from . import TestMonitoringMixin

Notification = load_model('openwisp_notifications', 'Notification')


class TestAdmin(TestMonitoringMixin, TestCase):
    def test_action_disable_notifications(self):
        m = self._create_general_metric(name='test')
        self._create_threshold(metric=m, operator='>', value=90, seconds=0)
        path = reverse('admin:monitoring_metric_changelist')
        self.client.force_login(self._get_admin())
        post_data = {
            '_selected_action': m.pk,
            'action': 'disable_notifications',
            'confirmation': 'Confirm',
        }
        self.assertRedirects(self.client.post(path, post_data), path)
        m.refresh_from_db()
        self.assertFalse(m.notifications_enabled)
        m.write(99)
        self.assertFalse(m.is_healthy)
        self.assertEqual(Notification.objects.count(), 0)

    def test_action_enable_notifications(self):
        m = self._create_general_metric(name='test', notifications_enabled=False)
        self._create_threshold(metric=m, operator='>', value=90, seconds=0)
        path = reverse('admin:monitoring_metric_changelist')
        self.client.force_login(self._get_admin())
        post_data = {
            '_selected_action': m.pk,
            'action': 'enable_notifications',
            'confirmation': 'Confirm',
        }
        self.assertRedirects(self.client.post(path, post_data), path)
        m.refresh_from_db()
        self.assertTrue(m.notifications_enabled)
        m.write(99)
        self.assertFalse(m.is_healthy)
        self.assertEqual(Notification.objects.count(), 1)

    def test_action_confirmation_page(self):
        m = self._create_general_metric(name='test')
        path = reverse('admin:monitoring_metric_changelist')
        self.client.force_login(self._get_admin())
        post_data = {
            '_selected_action': m.pk,
            'action': 'enable_notifications',
        }
        response = self.client.post(path, post_data)
        self.assertEqual(response.status_code, 200)
