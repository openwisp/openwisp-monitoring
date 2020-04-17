import swapper
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from ...monitoring.tests import TestMonitoringMixin
from ..admin import NotificationAdmin
from .test_helpers import MessagingRequest

Notification = swapper.load_model('notifications', 'Notification')
notification_queryset = Notification.objects.order_by('timestamp')


class MockSuperUser:
    def has_perm(self, perm):
        return True

    @property
    def pk(self):
        return 1


request = MessagingRequest()
request.user = MockSuperUser()


class TestAdmin(TestMonitoringMixin, TestCase):
    """
    Tests notifications in admin
    """

    def setUp(self):
        super().setUpClass()
        self.site = AdminSite()
        self.model_admin = NotificationAdmin(Notification, self.site)

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

    def test_mark_as_read_action(self):
        self._create_admin()
        m = self._create_general_metric(name='load')
        self._create_threshold(metric=m, operator='>', value=90, seconds=0)
        m.write(99)
        self.assertFalse(m.is_healthy)
        self.assertEqual(Notification.objects.count(), 1)
        ma = self.model_admin
        qs = Notification.objects.all()
        ma.mark_as_read(request, qs)
        m = list(request.get_messages())
        self.assertEqual(len(m), 1)
        self.assertEqual(str(m[0]), '1 notification was marked as read.')

    def test_callable_actor_object_link(self):
        self._create_admin()
        om = self._create_object_metric(name='load')
        self._create_threshold(metric=om, operator='>', value=90, seconds=0)
        om.write(99)
        n = notification_queryset.first()
        exp_actor_obj_link = '<a href="{0}" id="actor-object-url">{1}</a>'.format(
            reverse('admin:monitoring_metric_change', args=(n.actor_object_id,)),
            n.actor_object_id,
        )
        self.assertEqual(self.model_admin.actor_object_link(n), exp_actor_obj_link)

        n.actor_content_type = ContentType()
        self.assertEqual(self.model_admin.actor_object_link(n), n.actor_object_id)

        n.actor_content_type = None
        self.assertEqual(self.model_admin.actor_object_link(n), '-')

    def test_callable_action_object_link(self):
        self._create_admin()
        om = self._create_object_metric(name='load')
        self._create_threshold(metric=om, operator='>', value=90, seconds=0)
        om.write(99)
        n = notification_queryset.first()

        exp_action_obj_link = '<a href="{0}" id="action_object-object-url">{1}</a>'.format(
            reverse(
                'admin:monitoring_threshold_change', args=(n.action_object_object_id,)
            ),
            n.action_object_object_id,
        )
        self.assertEqual(self.model_admin.action_object_link(n), exp_action_obj_link)

        n.action_object_content_type = ContentType()
        self.assertEqual(
            self.model_admin.action_object_link(n), n.action_object_object_id
        )

        n.action_object_content_type = None
        self.assertEqual(self.model_admin.action_object_link(n), '-')

    def test_callable_target_object_link(self):
        self._create_admin()
        om = self._create_object_metric(name='load')
        self._create_threshold(metric=om, operator='>', value=90, seconds=0)
        om.write(99)
        n = notification_queryset.first()

        exp_target_obj_link = '<a href="{0}" id="target-object-url">{1}</a>'.format(
            reverse('admin:openwisp_users_user_change', args=(n.target_object_id,)),
            n.target_object_id,
        )
        self.assertEqual(self.model_admin.target_object_link(n), exp_target_obj_link)

        n.target_content_type = ContentType()
        self.assertEqual(self.model_admin.target_object_link(n), n.target_object_id)

        n.target_content_type = None
        self.assertEqual(self.model_admin.target_object_link(n), '-')

    def test_callable_related_object(self):
        self._create_admin()
        om = self._create_object_metric(name='load')
        self._create_threshold(metric=om, operator='>', value=90, seconds=0)
        om.write(99)
        n = notification_queryset.first()

        exp_related_obj_link = '<a href="{0}" id="related-object-url">{1}: {2}</a>'.format(
            reverse('admin:openwisp_users_user_change', args=(n.target_object_id,)),
            n.target_content_type.model,
            n.target,
        )
        self.assertEqual(self.model_admin.related_object(n), exp_related_obj_link)

        n.target_content_type = ContentType()
        self.assertEqual(self.model_admin.related_object(n), n.target_object_id)

        n.target_content_type = None
        self.assertEqual(self.model_admin.related_object(n), '-')
