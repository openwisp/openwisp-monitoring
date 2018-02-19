import json
import logging
from datetime import date, datetime, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.mail import send_mail
from django.core.validators import MaxValueValidator
from django.db import models
from django.db.models import Q
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import python_2_unicode_compatible
from django.utils.text import slugify
from django.utils.timezone import make_aware
from django.utils.translation import ugettext_lazy as _
from influxdb.exceptions import InfluxDBClientError
from notifications.models import Notification

from openwisp_utils.base import TimeStampedEditableModel

from .utils import query, write

User = get_user_model()
logger = logging.getLogger(__name__)


@python_2_unicode_compatible
class Metric(TimeStampedEditableModel):
    # TODO: questo va spostato su Threshold molto probabilmente
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

    @property
    def codename(self):
        """ identifier stored in timeseries db """
        return slugify(self.name).replace('-', '_')

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

    def write(self, value, time=None, database=None, check=True):
        """ write timeseries data """
        write(name=self.key,
              values={self.field_name: value},
              tags=self.tags,
              timestamp=time,
              database=database)
        # check can be disabled,
        # mostly for automated testing and debugging purposes
        if not check:
            return
        self.check_threshold(value, time)

    def read(self, since=None, limit=1, order=None):
        """ reads timeseries data """
        q = 'SELECT {fields} FROM {key}'.format(fields=self.field_name, key=self.key)
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

    def _clean_query(self):
        forbidden = ['drop', 'create', 'delete', 'alter', 'into']
        for word in forbidden:
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

    def get_query(self, time=None):
        if not time:
            time = date.today() - timedelta(days=6)
        m = self.metric
        params = dict(field_name=m.field_name,
                      key=m.key,
                      time=str(time))
        if m.object_id:
            params.update({'content_type': m.content_type_key,
                           'object_id': m.object_id})
        q = self.query.format(**params)
        return "{0} tz('{1}')".format(q, settings.TIME_ZONE)

    def read(self, decimal_places=2):
        graphs = {}
        x = []
        try:
            points = list(query(self.get_query(), epoch='s').get_points())
        except InfluxDBClientError as e:
            logging.error(e, exc_info=True)
            return False
        for point in points:
            for key, value in point.items():
                if key == 'time':
                    continue
                graphs.setdefault(key, [])
                if decimal_places:
                    value = round(value, decimal_places)
                graphs[key].append(value)
            time = datetime.fromtimestamp(point['time']) \
                           .strftime('%Y-%m-%d')
            x.append(time)
        # transform data so its order is not random
        return {'x': x, 'graphs': sorted(graphs.items())}

    @property
    def json(self, **kwargs):
        return json.dumps(self.read(), **kwargs)


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
    if not created or not instance.recipient.notificationuser.email:
        return
    subject = instance.data.get('email_subject') or instance.description[0:24]
    url = instance.data.get('url')
    description = instance.description
    if url:
        description += '\n\nFor more information see {0}.'.format(url)
    send_mail(subject, description,
              settings.DEFAULT_FROM_EMAIL,
              [instance.recipient.email])
