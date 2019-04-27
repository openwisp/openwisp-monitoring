import swapper
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from ...monitoring.tests import TestMonitoringMixin

Notification = swapper.load_model('notifications', 'Notification')


class TestAdminNotifications(TestMonitoringMixin, TestCase):
    """
    Tests notifications in admin
    """
    def _login_admin(self):
        User = get_user_model()
        u = User.objects.create_superuser('admin', 'admin', 'test@test.com')
        self.client.force_login(u)
        return u

    _url = reverse('admin:notifications_notification_changelist')
    _cache_key = Notification.COUNT_CACHE_KEY

    def _expected_output(self, count=0):
        if count > 0:
            return '<span>{0}</span>'.format(count)
        return 'id="monitoring-notifications">'

    def test_zero_notifications(self):
        self._login_admin()
        r = self.client.get(self._url)
        self.assertContains(r, self._expected_output())

    def test_non_zero_notifications(self):
        self._login_admin()
        m = self._create_general_metric()
        self._create_threshold(metric=m, operator='>', value=0)
        m.write(1)
        r = self.client.get(self._url)
        self.assertContains(r, self._expected_output(1))

    def test_cached_value(self):
        u = self._login_admin()
        self.client.get(self._url)
        cache_key = self._cache_key.format(u.pk)
        self.assertEqual(cache.get(cache_key), 0)
        return cache_key

    def test_cached_invalidation(self):
        cache_key = self.test_cached_value()
        m = self._create_general_metric()
        self._create_threshold(metric=m, operator='>', value=0)
        m.write(1)
        self.assertIsNone(cache.get(cache_key))
        self.client.get(self._url)
        self.assertEqual(cache.get(cache_key), 1)
