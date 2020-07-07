import json
import logging
from datetime import date, datetime, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.validators import MaxValueValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.utils.timezone import make_aware
from django.utils.translation import gettext_lazy as _
from openwisp_notifications.signals import notify
from pytz import timezone as tz
from swapper import get_model_name

from openwisp_utils.base import TimeStampedEditableModel

from ...db import default_chart_query, timeseries_db
from ..charts import (
    CHART_CONFIGURATION_CHOICES,
    DEFAULT_COLORS,
    get_chart_configuration,
)
from ..exceptions import InvalidChartConfigException, InvalidMetricConfigException
from ..metrics import get_metric_configuration, get_metric_configuration_choices
from ..signals import post_metric_write, pre_metric_write, threshold_crossed

User = get_user_model()
logger = logging.getLogger(__name__)


class AbstractMetric(TimeStampedEditableModel):
    METRICS = get_metric_configuration()
    name = models.CharField(max_length=64)
    key = models.SlugField(
        max_length=64, blank=True, help_text=_('leave blank to determine automatically')
    )
    field_name = models.CharField(max_length=16, default='value')
    configuration = models.CharField(
        max_length=16, null=True, choices=get_metric_configuration_choices()
    )
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, null=True, blank=True
    )
    object_id = models.CharField(max_length=36, db_index=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    # NULL means the health has yet to be assessed
    is_healthy = models.BooleanField(default=None, null=True, blank=True, db_index=True)

    class Meta:
        abstract = True
        unique_together = ('key', 'field_name', 'content_type', 'object_id')

    def __str__(self):
        obj = self.content_object
        if not obj:
            return self.name
        model_name = obj.__class__.__name__
        return '{0} ({1}: {2})'.format(self.name, model_name, obj)

    def clean(self):
        if (
            self.field_name == 'value'
            and self.config_dict['field_name'] != '{field_name}'
        ):
            self.field_name = self.config_dict['field_name']
        if self.key:
            return
        elif self.config_dict['key'] != '{key}':
            self.key = self.config_dict['key']
        else:
            self.key = self.codename

    def full_clean(self, *args, **kwargs):
        if not self.name:
            self.name = self.config_dict['name']
        # clean up key before field validation
        self.key = self._makekey(self.key)
        return super().full_clean(*args, **kwargs)

    @classmethod
    def _get_or_create(cls, **kwargs):
        """
        like ``get_or_create`` method of django model managers
        but with validation before creation
        """
        if 'key' in kwargs:
            kwargs['key'] = cls._makekey(kwargs['key'])
        try:
            lookup_kwargs = kwargs.copy()
            if lookup_kwargs.get('name'):
                del lookup_kwargs['name']
            metric = cls.objects.get(**lookup_kwargs)
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

    @property
    def config_dict(self):
        try:
            return self.METRICS[self.configuration]
        except KeyError:
            raise InvalidMetricConfigException(
                f'Invalid metric configuration: "{self.configuration}"'
            )

    @property
    def related_fields(self):
        return self.config_dict.get('related_fields', [])

    # TODO: This method needs to be refactored when adding the other db
    @staticmethod
    def _makekey(value):
        """ makes value suited for InfluxDB key """
        value = value.replace('.', '_')
        return slugify(value).replace('-', '_')

    @property
    def tags(self):
        if self.content_type and self.object_id:
            return {
                'content_type': self.content_type_key,
                'object_id': str(self.object_id),
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
            alert_settings = self.alertsettings
        except ObjectDoesNotExist:
            return
        crossed = alert_settings._is_crossed_by(value, time)
        first_time = False
        # situation has not changed
        if (not crossed and self.is_healthy) or (crossed and self.is_healthy is False):
            return
        # problem: not within threshold limit
        elif crossed and self.is_healthy in [True, None]:
            if self.is_healthy is None:
                first_time = True
            self.is_healthy = False
            notification_type = 'threshold_crossed'
        # ok: returned within threshold limit
        elif not crossed and self.is_healthy is False:
            self.is_healthy = True
            notification_type = 'threshold_recovery'
        # First metric write within threshold
        elif not crossed and self.is_healthy is None:
            self.is_healthy = True
            first_time = True
        self.save()
        threshold_crossed.send(
            sender=self.__class__,
            alert_settings=alert_settings,
            metric=self,
            target=self.content_object,
            first_time=first_time,
        )
        # First metric write and within threshold, do not raise alert
        if first_time and self.is_healthy:
            return
        self._notify_users(notification_type, alert_settings)

    def write(self, value, time=None, database=None, check=True, extra_values=None):
        """ write timeseries data """
        values = {self.field_name: value}
        if extra_values and isinstance(extra_values, dict):
            for key in extra_values.keys():
                if not self.related_fields or key not in self.related_fields:
                    raise ValueError(f'"{key}" not defined in metric configuration')
            values.update(extra_values)
        signal_kwargs = dict(sender=self.__class__, metric=self, values=values)
        pre_metric_write.send(**signal_kwargs)
        timeseries_db.write(
            name=self.key,
            values=values,
            tags=self.tags,
            timestamp=time,
            database=database,
        )
        post_metric_write.send(**signal_kwargs)
        # check can be disabled,
        # mostly for automated testing and debugging purposes
        if not check:
            return
        self.check_threshold(value, time)

    def read(self, **kwargs):
        """ reads timeseries data """
        return timeseries_db.read(
            key=self.key, fields=self.field_name, tags=self.tags, **kwargs
        )

    def _notify_users(self, notification_type, alert_settings):
        """ creates notifications for users """
        opts = dict(sender=self, type=notification_type, action_object=alert_settings)
        if self.content_object is not None:
            opts['target'] = self.content_object
        notify.send(**opts)


class AbstractChart(TimeStampedEditableModel):
    metric = models.ForeignKey(
        get_model_name('monitoring', 'Metric'), on_delete=models.CASCADE
    )
    configuration = models.CharField(
        max_length=16, null=True, choices=CHART_CONFIGURATION_CHOICES
    )
    GROUP_MAP = {
        '1d': '10m',
        '3d': '20m',
        '7d': '1h',
        '30d': '24h',
        '365d': '24h',
    }
    DEFAULT_TIME = '7d'

    class Meta:
        abstract = True

    def __str__(self):
        return str(self.label) or self.metric.name

    def clean(self):
        self._clean_query()

    def _clean_query(self):
        try:
            timeseries_db.validate_query(self.query)
            timeseries_db.query(self.get_query())
        except timeseries_db.client_error as e:
            raise ValidationError({'configuration': e}) from e
        except InvalidChartConfigException as e:
            raise ValidationError({'configuration': str(e)}) from e

    @property
    def config_dict(self):
        try:
            return get_chart_configuration()[self.configuration]
        except KeyError as e:
            raise InvalidChartConfigException(
                f'Invalid chart configuration: "{self.configuration}"'
            ) from e

    @property
    def type(self):
        return self.config_dict['type']

    @property
    def label(self):
        return self.config_dict.get('label') or self.title

    @property
    def description(self):
        return self.config_dict['description'].format(metric=self.metric)

    @property
    def title(self):
        return self.config_dict['title']

    @property
    def summary_labels(self):
        return self.config_dict.get('summary_labels')

    @property
    def order(self):
        return self.config_dict['order']

    @property
    def colors(self):
        colors = self.config_dict.get('colors')
        if not colors and self.summary_labels:
            summary_length = len(self.summary_labels)
            return DEFAULT_COLORS[0:summary_length]
        return colors

    @property
    def colorscale(self):
        return self.config_dict.get('colorscale')

    @property
    def unit(self):
        return self.config_dict.get('unit')

    @property
    def query(self):
        query = self.config_dict['query']
        if query:
            return query[timeseries_db.backend_name]
        return self._default_query

    @property
    def top_fields(self):
        return self.config_dict.get('top_fields', None)

    @property
    def _default_query(self):
        q = default_chart_query[0]
        if self.metric.object_id:
            q += default_chart_query[1]
        return q

    def get_query(
        self,
        time=DEFAULT_TIME,
        summary=False,
        fields=None,
        query=None,
        timezone=settings.TIME_ZONE,
    ):
        query = query or self.query
        params = self._get_query_params(time)
        return timeseries_db.get_query(
            self.type, params, time, self.GROUP_MAP, summary, fields, query, timezone
        )

    def get_top_fields(self, number):
        """
        Returns list of top ``number`` of fields (highest sum) of a
        measurement in the specified time range (descending order).
        """
        q = self._default_query.replace('{field_name}', '{fields}')
        params = self._get_query_params(self.DEFAULT_TIME)
        return timeseries_db._get_top_fields(
            query=q,
            chart_type=self.type,
            group_map=self.GROUP_MAP,
            number=number,
            params=params,
            time=self.DEFAULT_TIME,
        )

    def _get_query_params(self, time):
        m = self.metric
        params = dict(field_name=m.field_name, key=m.key, time=self._get_time(time))
        if m.object_id:
            params.update(
                {'content_type': m.content_type_key, 'object_id': m.object_id}
            )
        return params

    def _get_time(self, time):
        if not isinstance(time, str):
            return str(time)
        if time in self.GROUP_MAP.keys():
            days = int(time.strip('d'))
            now = timezone.now()
            if days > 3:
                now = date(now.year, now.month, now.day)
            if days == 7:
                # subtract one day because we want to include
                # the current day in the time range
                days -= 1
            time = str(now - timedelta(days=days))[0:19]
        return time

    def read(
        self,
        decimal_places=2,
        time=DEFAULT_TIME,
        x_axys=True,
        timezone=settings.TIME_ZONE,
    ):
        traces = {}
        if x_axys:
            x = []
        try:
            query_kwargs = dict(time=time, timezone=timezone)
            if self.top_fields:
                fields = self.get_top_fields(self.top_fields)
                data_query = self.get_query(fields=fields, **query_kwargs)
                summary_query = self.get_query(
                    fields=fields, summary=True, **query_kwargs
                )
            else:
                data_query = self.get_query(**query_kwargs)
                summary_query = self.get_query(summary=True, **query_kwargs)
            points = timeseries_db.get_list_query(data_query)
            summary = timeseries_db.get_list_query(summary_query)
        except timeseries_db.client_error as e:
            logging.error(e, exc_info=True)
            raise e
        for point in points:
            for key, value in point.items():
                if key == 'time':
                    continue
                traces.setdefault(key, [])
                if decimal_places and isinstance(value, (int, float)):
                    value = self._round(value, decimal_places)
                traces[key].append(value)
            time = datetime.fromtimestamp(point['time'], tz=tz(timezone)).strftime(
                '%Y-%m-%d %H:%M'
            )
            if x_axys:
                x.append(time)
        # prepare result to be returned
        # (transform chart data so its order is not random)
        result = {'traces': sorted(traces.items())}
        if x_axys:
            result['x'] = x
        # add summary
        if len(summary) > 0:
            result['summary'] = {}
            for key, value in summary[0].items():
                if key == 'time':
                    continue
                if not timeseries_db.validate_query(self.query):
                    value = None
                elif value:
                    value = self._round(value, decimal_places)
                result['summary'][key] = value
        return result

    def json(self, time=DEFAULT_TIME, **kwargs):
        try:
            # unit needs to be passed for chart_inline
            data = self.read(time=time)
            data.update({'unit': self.unit})
            return json.dumps(data, **kwargs)
        except KeyError:
            # TODO: this should be improved
            pass

    @staticmethod
    def _round(value, decimal_places):
        """
        rounds value if it makes sense
        """
        control = 1.0 / 10 ** decimal_places
        if value < control:
            decimal_places += 2
        return round(value, decimal_places)


class AbstractAlertSettings(TimeStampedEditableModel):
    _SECONDS_MAX = 60 * 60 * 24 * 7  # 7 days
    _SECONDS_HELP = (
        'for how long should the alert_settings value be crossed before '
        'triggering an alert? The maximum allowed is {0} seconds '
        '({1} days)'.format(_SECONDS_MAX, int(_SECONDS_MAX / 60 / 60 / 24))
    )
    _ALERTSETTINGS_OPERATORS = (('<', _('less than')), ('>', _('greater than')))
    metric = models.OneToOneField(
        get_model_name('monitoring', 'Metric'), on_delete=models.CASCADE
    )
    operator = models.CharField(max_length=1, choices=_ALERTSETTINGS_OPERATORS)
    value = models.FloatField(help_text=_('threshold value'))
    seconds = models.PositiveIntegerField(
        default=0, validators=[MaxValueValidator(604800)], help_text=_(_SECONDS_HELP)
    )

    class Meta:
        abstract = True
        verbose_name = _('Alert settings')
        verbose_name_plural = verbose_name

    def _value_crossed(self, current_value):
        threshold_value = self.value
        method = '__gt__' if self.operator == '>' else '__lt__'
        if isinstance(current_value, int):
            current_value = float(current_value)
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
        if value_crossed and self.seconds == 0:
            return True
        if time is None:
            # retrieves latest measurements up to the maximum
            # threshold in seconds allowed plus a small margin
            since = 'now() - {0}s'.format(int(self._SECONDS_MAX * 1.05))
            points = self.metric.read(since=since, limit=None, order='-time')
            # loop on each measurement starting from the most recent
            for i, point in enumerate(points):
                # skip the first point because it was just added before this
                # check started and its value coincides with ``current_value``
                if i < 1:
                    continue
                if not self._value_crossed(point[self.metric.field_name]):
                    return False
                if self._time_crossed(
                    make_aware(datetime.fromtimestamp(point['time']))
                ):
                    return True
                # if threshold value is crossed but threshold time is not
                # keep iterating (explicit continue statement added
                #                 for better algorithm readability)
                continue
            time = timezone.now()
        if self._time_crossed(time):
            return True
        return False
