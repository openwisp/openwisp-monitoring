import json
import logging
import re
from datetime import date, datetime, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.mail import send_mail
from django.core.validators import MaxValueValidator
from django.db import models
from django.db.models import Q
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import python_2_unicode_compatible
from django.utils.text import slugify
from django.utils.timezone import make_aware
from django.utils.translation import ugettext_lazy as _
from influxdb.exceptions import InfluxDBClientError
from notifications.models import Notification
from pytz import timezone as tz

from openwisp_utils.base import TimeStampedEditableModel

from .utils import NOTIFICATIONS_COUNT_CACHE_KEY, query, write

User = get_user_model()
logger = logging.getLogger(__name__)


@python_2_unicode_compatible
class Metric(TimeStampedEditableModel):
    # TODO: this probably should be moved to Threshold
    HEALTH_CHOICES = (('ok', _('ok')),
                      ('problem', _('problem')))
    health = models.CharField(max_length=8,
                              choices=HEALTH_CHOICES,
                              default=HEALTH_CHOICES[0][0])
    name = models.CharField(max_length=64)
    description = models.TextField(blank=True)
    key = models.SlugField(max_length=64,
                           blank=True,
                           help_text=_('leave blank to determine automatically'))
    field_name = models.CharField(max_length=16, default='value')
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE,
                                     null=True, blank=True)
    object_id = models.CharField(max_length=36, db_index=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        unique_together = ('key', 'field_name', 'content_type', 'object_id')

    def __str__(self):
        obj = self.content_object
        if not obj:
            return self.name
        model_name = obj.__class__.__name__
        return '{0} ({1}: {2})'.format(self.name, model_name, obj)

    def clean(self):
        if not self.key:
            self.key = self.codename

    def full_clean(self, *args, **kwargs):
        # clean up key before field validation
        self.key = self._makekey(self.key)
        return super(Metric, self).full_clean(*args, **kwargs)

    @classmethod
    def _get_or_create(cls, **kwargs):
        """
        like ``get_or_create`` method of django model managers
        but with validation before creationg
        """
        if 'key' in kwargs:
            kwargs['key'] = cls._makekey(kwargs['key'])
        try:
            metric = cls.objects.get(**kwargs)
            created = False
        except cls.DoesNotExist:
            metric = cls(**kwargs)
            metric.full_clean()
            metric.save()
            created = True
        return metric, created

    @property
    def codename(self):
        """ identifier stored in timeseries db """
        return self._makekey(self.name)

    @staticmethod
    def _makekey(value):
        """ makes value suited for influxdb key """
        value = value.replace('.', '_')
        return slugify(value).replace('-', '_')

    @property
    def tags(self):
        if self.content_type and self.object_id:
            return {
                'content_type': self.content_type_key,
                'object_id': str(self.object_id)
            }
        return {}

    @property
    def content_type_key(self):
        try:
            return '.'.join(self.content_type.natural_key())
        except AttributeError:
            return None

    def check_threshold(self, value, time=None):
        """
        checks if the threshold is crossed
        and notifies users accordingly
        """
        try:
            threshold = self.threshold
        except ObjectDoesNotExist:
            return
        crossed = threshold._is_crossed_by(value, time)
        health_ok = self.health == 'ok'
        # don't notify is situation hasn't changed
        if (not crossed and health_ok) or \
           (crossed and not health_ok):
            return
        # problem!
        elif crossed and health_ok:
            self.health = 'problem'
            level = 'warning'
            verb = 'crossed threshold limit'
        # back to normal
        elif not crossed and not health_ok:
            self.health = 'ok'
            level = 'info'
            verb = 'returned within threshold limit'
        self.save()
        self._notify_users(level, verb, threshold)

    def write(self, value, time=None, database=None, check=True, extra_values=None):
        """ write timeseries data """
        values = {self.field_name: value}
        if extra_values and isinstance(extra_values, dict):
            values.update(extra_values)
        write(name=self.key,
              values=values,
              tags=self.tags,
              timestamp=time,
              database=database)
        # check can be disabled,
        # mostly for automated testing and debugging purposes
        if not check:
            return
        self.check_threshold(value, time)

    def read(self, since=None, limit=1, order=None, extra_fields=None):
        """ reads timeseries data """
        fields = self.field_name
        if extra_fields:
            fields = ', '.join([fields] + extra_fields)
        q = 'SELECT {fields} FROM {key}'.format(fields=fields, key=self.key)
        tags = self.tags
        conditions = []
        if since:
            conditions.append("time >= {0}".format(since))
        if tags:
            conditions.append(' AND '.join(["{0} = '{1}'".format(*tag)
                                            for tag in tags.items()]))
        if conditions:
            conditions = 'WHERE %s' % ' AND '.join(conditions)
            q = '{0} {1}'.format(q, conditions)
        if order:
            q = '{0} ORDER BY {1}'.format(q, order)
        if limit:
            q = '{0} LIMIT {1}'.format(q, limit)
        return list(query(q, epoch='s').get_points())

    def _notify_users(self, level, verb, threshold):
        """ creates notifications for users """
        opts = dict(actor=self,
                    level=level,
                    verb=verb,
                    action_object=threshold)
        if self.content_object is None:
            opts['actor'] = self
            target_org = None
        else:
            opts['target'] = self.content_object
            target_org = getattr(opts['target'], 'organization_id', None)
        self._set_extra_notification_opts(opts)
        # retrieve superusers
        where = Q(is_superuser=True)
        # if target_org is specified, retrieve also
        # staff users that are member of the org
        if target_org:
            where = (
                where | (
                    Q(is_staff=True) &
                    Q(openwisp_users_organization=target_org)
                )
            )
        # only retrieve users which have the receive flag active
        where = where & Q(notificationuser__receive=True)
        # perform query
        qs = User.objects.select_related('notificationuser') \
                         .order_by('date_joined') \
                         .filter(where)
        for user in qs:
            n = Notification(**opts)
            n.recipient = user
            n.full_clean()
            n.save()

    def _set_extra_notification_opts(self, opts):
        verb = opts['verb']
        target = opts.get('target')
        metric = str(self).capitalize()
        status = 'PROBLEM' if self.health == 'problem' else 'RECOVERY'
        info = ''
        t = self.threshold
        if self.health == 'problem':
            info = ' ({0} {1})'.format(t.get_operator_display(), t.value)
        desc = 'Metric "{metric}" {verb}{info}.'.format(status=status, metric=metric,
                                                        verb=verb, info=info)
        opts['description'] = desc
        opts['data'] = {
            'email_subject': '[{status}] {metric}'.format(status=status, metric=metric)
        }
        if target and target.__class__.__name__.lower() == 'device':
            opts['data']['url'] = reverse('admin:config_device_change', args=[target.pk])


@python_2_unicode_compatible
class Graph(TimeStampedEditableModel):
    metric = models.ForeignKey(Metric, on_delete=models.CASCADE)
    description = models.CharField(max_length=64, blank=True)
    query = models.TextField(blank=True)

    def __str__(self):
        return self.description or self.metric.name

    def clean(self):
        if not self.metric:
            return
        if not self.description:
            self.description = self.metric.name
        if not self.query:
            self.query = self._default_query
        self._clean_query()

    _FORBIDDEN = ['drop', 'create', 'delete', 'alter', 'into']
    _AGGREGATE = [
        'COUNT', 'DISTINCT', 'INTEGRAL', 'MEAN', 'MEDIAN', 'MODE',
        'SPREAD', 'STDDEV', 'SUM', 'BOTTOM', 'FIRST', 'LAST', 'MAX',
        'MIN', 'PERCENTILE', 'SAMPLE', 'TOP', 'CEILING', 'CUMULATIVE_SUM',
        'DERIVATIVE', 'DIFFERENCE', 'ELAPSED', 'FLOOR', 'HISTOGRAM',
        'MOVING_AVERAGE', 'NON_NEGATIVE_DERIVATIVE', 'HOLT_WINTERS'
    ]
    GROUP_MAP = {
        '1d': '10m',
        '3d': '20m',
        '7d': '1h',
        '30d': '24h',
        '365d': '24h'
    }
    DEFAULT_TIME = '7d'

    def _clean_query(self):
        for word in self._FORBIDDEN:
            if word in self.query.lower():
                msg = _('the word "{0}" is not allowed').format(word.upper())
                raise ValidationError({'query': msg})
        # try query
        try:
            query(self.get_query())
        except InfluxDBClientError as e:
            raise ValidationError({'query': e})

    @property
    def _default_query(self):
        q = "SELECT {field_name} FROM {key} WHERE " \
            "time >= '{time}'"
        if self.metric.object_id:
            q += " AND content_type = '{content_type}'" \
                 " AND object_id = '{object_id}'"
        return q

    def get_query(self, time=DEFAULT_TIME, summary=False, timezone=settings.TIME_ZONE):
        m = self.metric
        params = dict(field_name=m.field_name,
                      key=m.key,
                      time=self._get_time(time))
        if m.object_id:
            params.update({'content_type': m.content_type_key,
                           'object_id': m.object_id})
        q = self.query.format(**params)
        q = self._group_by(q, time, strip=summary)
        return "{0} tz('{1}')".format(q, timezone)

    def _get_time(self, time):
        if not isinstance(time, str):
            return str(time)
        if time in self.GROUP_MAP.keys():
            days = int(time.strip('d'))
            now = timezone.now()
            if days > 3:
                now = date(now.year, now.month, now.day)
            if days is 7:
                # subtract one day because we want to include
                # the current day in the time range
                days -= 1
            time = str(now - timedelta(days=days))[0:19]
        return time

    def _is_aggregate(self, q):
        q = q.upper()
        for word in self._AGGREGATE:
            if word in q:
                return True
        return False

    _group_by_regex = re.compile('GROUP BY time\(\w+\)', flags=re.IGNORECASE)

    def _group_by(self, query, time, strip=False):
        if not self._is_aggregate(query):
            return query
        if not strip:
            value = self.GROUP_MAP[time]
            group_by = 'GROUP BY time({0})'.format(value)
        else:
            # can be empty when getting summaries
            group_by = ''
        if 'GROUP BY' not in query.upper():
            query = '{0} {1}'.format(query, group_by)
        else:
            query = re.sub(self._group_by_regex, group_by, query)
        return query

    def read(self, decimal_places=2, time=DEFAULT_TIME, x_axys=True, timezone=settings.TIME_ZONE):
        traces = {}
        if x_axys:
            x = []
        try:
            query_kwargs = dict(time=time, timezone=timezone)
            points = list(query(self.get_query(**query_kwargs), epoch='s').get_points())
            query_kwargs['summary'] = True
            summary = list(query(self.get_query(**query_kwargs), epoch='s').get_points())
        except InfluxDBClientError as e:
            logging.error(e, exc_info=True)
            raise e
        for point in points:
            for key, value in point.items():
                if key == 'time':
                    continue
                traces.setdefault(key, [])
                if decimal_places and isinstance(value, (int, float)):
                    value = round(value, decimal_places)
                traces[key].append(value)
            time = datetime.fromtimestamp(point['time'], tz=tz(timezone)) \
                           .strftime('%Y-%m-%d %H:%M')
            if x_axys:
                x.append(time)
        # prepare result to be returned
        # (transform graph data so its order is not random)
        result = {'traces': sorted(traces.items())}
        if x_axys:
            result['x'] = x
        # add summary
        if len(summary) > 0:
            result['summary'] = {}
            for key, value in summary[0].items():
                if key == 'time':
                    continue
                result['summary'][key] = round(value, decimal_places)
        return result

    def json(self, time=DEFAULT_TIME, **kwargs):
        return json.dumps(self.read(time=time), **kwargs)


class Threshold(TimeStampedEditableModel):
    _SECONDS_MAX = 60 * 60 * 24 * 7  # 7 days
    _SECONDS_HELP = 'for how long should the threshold value be crossed before ' \
                    'triggering an alert? The maximum allowed is {0} seconds ' \
                    '({1} days)'.format(_SECONDS_MAX, int(_SECONDS_MAX / 60 / 60 / 24))
    _THRESHOLD_OPERATORS = (('<', _('less than')),
                            ('>', _('greater than')))
    metric = models.OneToOneField(Metric, on_delete=models.CASCADE)
    operator = models.CharField(max_length=1, choices=_THRESHOLD_OPERATORS)
    value = models.IntegerField(help_text=_('threshold value'))
    seconds = models.PositiveIntegerField(default=0,
                                          validators=[MaxValueValidator(604800)],
                                          help_text=_(_SECONDS_HELP))

    def _value_crossed(self, current_value):
        threshold_value = self.value
        method = '__gt__' if self.operator == '>' else '__lt__'
        return getattr(current_value, method)(threshold_value)

    def _time_crossed(self, time):
        threshold_time = timezone.now() - timedelta(seconds=self.seconds)
        return time < threshold_time

    def _is_crossed_by(self, current_value, time=None):
        """ do current_value and time cross the threshold? """
        value_crossed = self._value_crossed(current_value)
        if value_crossed is NotImplemented:
            raise ValueError('Supplied value type not suppported')
        if not value_crossed:
            return False
        if value_crossed and self.seconds is 0:
            return True
        if time is None:
            # retrieves latest measurements up to the maximum
            # threshold in seconds allowed plus a small margin
            since = 'now() - {0}s'.format(int(self._SECONDS_MAX * 1.05))
            points = self.metric.read(since=since, limit=None, order='time DESC')
            # loop on each measurement starting from the most recent
            for i, point in enumerate(points):
                # skip the first point because it was just added before this
                # check started and its value coincides with ``current_value``
                if i < 1:
                    continue
                if not self._value_crossed(point[self.metric.field_name]):
                    return False
                if self._time_crossed(make_aware(datetime.fromtimestamp(point['time']))):
                    return True
                # if threshold value is crossed but threshold time is not
                # keep iterating (explicit continue statement added
                #                 for better algorithm readability)
                continue
            time = timezone.now()
        if self._time_crossed(time):
            return True
        return False


class NotificationUser(TimeStampedEditableModel):
    _RECEIVE_HELP = 'note: non-superadmin users receive ' \
                    'notifications only for organizations ' \
                    'of which they are member of.'
    user = models.OneToOneField(settings.AUTH_USER_MODEL,
                                on_delete=models.CASCADE)
    receive = models.BooleanField(_('receive notifications'),
                                  default=True,
                                  help_text=_(_RECEIVE_HELP))
    email = models.BooleanField(_('email notifications'),
                                default=True,
                                help_text=_(_RECEIVE_HELP))

    class Meta:
        verbose_name = _('user notification settings')
        verbose_name_plural = verbose_name

    def save(self, *args, **kwargs):
        if not self.receive:
            self.email = self.receive
        return super(NotificationUser, self).save(*args, **kwargs)


@receiver(post_save, sender=User, dispatch_uid='create_notificationuser')
def create_notificationuser_settings(sender, instance, **kwargs):
    try:
        instance.notificationuser
    except ObjectDoesNotExist:
        NotificationUser.objects.create(user=instance)


@receiver(post_save, sender=Notification, dispatch_uid='send_email_notification')
def send_email_notification(sender, instance, created, **kwargs):
    # ensure we need to sending email or stop
    if not created or (not instance.recipient.notificationuser.email or
                       not instance.recipient.email):
        return
    # send email
    subject = instance.data.get('email_subject') or instance.description[0:24]
    url = instance.data.get('url')
    description = instance.description
    if url:
        description += '\n\nFor more information see {0}.'.format(url)
    send_mail(subject, description,
              settings.DEFAULT_FROM_EMAIL,
              [instance.recipient.email])
    # flag as emailed
    instance.emailed = True
    instance.save()


@receiver(post_save, sender=Notification, dispatch_uid='clear_notification_cache_saved')
@receiver(post_delete, sender=Notification, dispatch_uid='clear_notification_cache_deleted')
def clear_notification_cache(sender, instance, **kwargs):
    # invalidate cache for user
    cache.delete(NOTIFICATIONS_COUNT_CACHE_KEY.format(instance.recipient.pk))
