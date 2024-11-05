import json
import logging
from collections import OrderedDict
from copy import deepcopy
from datetime import date, datetime, timedelta

from cache_memoize import cache_memoize
from dateutil.parser import parse as parse_date
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.validators import MaxValueValidator
from django.db import IntegrityError, models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from jsonfield import JSONField
from openwisp_notifications.signals import notify
from pytz import timezone as tz
from pytz import utc
from swapper import get_model_name

from openwisp_monitoring.monitoring.utils import clean_timeseries_data_key
from openwisp_utils.base import TimeStampedEditableModel

from ...db import default_chart_query, timeseries_db
from ...settings import CACHE_TIMEOUT, DEFAULT_CHART_TIME
from ..configuration import (
    CHART_CONFIGURATION_CHOICES,
    DEFAULT_COLORS,
    METRIC_CONFIGURATION_CHOICES,
    get_chart_configuration,
    get_metric_configuration,
)
from ..exceptions import InvalidChartConfigException, InvalidMetricConfigException
from ..signals import pre_metric_write, threshold_crossed
from ..tasks import _timeseries_batch_write, _timeseries_write, delete_timeseries

User = get_user_model()
logger = logging.getLogger(__name__)


def get_metric_cache_key(*args, **kwargs):
    cache_key = [
        'get_or_create_metric',
    ]
    cache_key.append(
        'key={}'.format(
            kwargs.get('key', kwargs.get('name', kwargs.get('configuration')))
        )
    )
    for key in ['content_type_id', 'object_id', 'configuration']:
        cache_key.append('{}={}'.format(key, kwargs.get(key)))
    cache_key.append('main_tags={}'.format(kwargs.get('main_tags', OrderedDict())))
    cache_key = ','.join(cache_key)
    return cache_key


class AbstractMetric(TimeStampedEditableModel):
    name = models.CharField(max_length=64)
    key = models.SlugField(
        max_length=64, blank=True, help_text=_('leave blank to determine automatically')
    )
    field_name = models.CharField(
        max_length=16,
        default='value',
        blank=True,
        help_text=_('leave blank to determine automatically'),
    )
    configuration = models.CharField(
        max_length=16, null=True, choices=METRIC_CONFIGURATION_CHOICES
    )
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, null=True, blank=True
    )
    object_id = models.CharField(max_length=36, db_index=True, blank=True, null=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    main_tags = JSONField(
        _('main tags'),
        default=dict,
        blank=True,
        load_kwargs={'object_pairs_hook': OrderedDict},
        dump_kwargs={'indent': 4},
        db_index=True,
    )
    extra_tags = JSONField(
        _('extra tags'),
        default=dict,
        blank=True,
        load_kwargs={'object_pairs_hook': OrderedDict},
        dump_kwargs={'indent': 4},
    )
    # NULL means the health has yet to be assessed
    is_healthy = models.BooleanField(default=None, null=True, blank=True, db_index=True)
    # Like "is_healthy", but respects tolerance of alert settings
    is_healthy_tolerant = models.BooleanField(default=None, null=True, blank=True)

    class Meta:
        abstract = True
        unique_together = (
            'key',
            'field_name',
            'content_type',
            'object_id',
            'main_tags',
        )

    def __str__(self):
        obj = self.content_object
        if not obj:
            return self.name
        model_name = obj.__class__.__name__
        return '{0} ({1}: {2})'.format(self.name, model_name, obj)

    def __setattr__(self, attrname, value):
        if attrname in ['main_tags', 'extra_tags']:
            value = self._sort_dict(value)
        return super().__setattr__(attrname, value)

    def clean(self):
        if self.key:
            return
        elif self.config_dict['key'] != '{key}':
            self.key = self.config_dict['key']
        else:
            self.key = self.codename

    def validate_alert_fields(self):
        # When field_name is not provided while creating a metric
        # then use config_dict['field_name] as metric field_name
        if self.config_dict['field_name'] != '{field_name}':
            if self.field_name in ['', 'value']:
                self.field_name = self.config_dict['field_name']
                return
            # field_name must be one of the metric fields
            alert_fields = [self.config_dict['field_name']] + self.related_fields
            if self.field_name not in alert_fields:
                raise ValidationError(
                    f'"{self.field_name}" must be one of the following metric fields ie. {alert_fields}'
                )

    def full_clean(self, *args, **kwargs):
        # The name of the metric will be the same as the
        # configuration chosen by the user only when the
        # name field is empty (useful for AlertSettingsInline)
        if not self.name:
            self.name = self.get_configuration_display()
        # clean up key before field validation
        self.key = self._makekey(self.key)
        # validate metric field_name for alerts
        self.validate_alert_fields()
        return super().full_clean(*args, **kwargs)

    @classmethod
    def post_delete_receiver(cls, instance, *args, **kwargs):
        delete_timeseries.delay(instance.key, instance.tags)

    @classmethod
    def _get_or_create(
        cls,
        **kwargs,
    ):
        """Gets or creates a metric.

        Like ``get_or_create`` method of django model managers but with
        validation before creation.
        """
        if 'key' in kwargs:
            kwargs['key'] = cls._makekey(kwargs['key'])
        try:
            lookup_kwargs = deepcopy(kwargs)
            if lookup_kwargs.get('name'):
                del lookup_kwargs['name']
            extra_tags = lookup_kwargs.pop('extra_tags', {})
            metric = cls._get_metric(**lookup_kwargs)
            created = False
            if extra_tags != metric.extra_tags:
                metric.extra_tags.update(kwargs['extra_tags'])
                metric.extra_tags = cls._sort_dict(metric.extra_tags)
                metric.save()
        except cls.DoesNotExist:
            try:
                metric = cls(**kwargs)
                metric.full_clean()
                metric.save()
                created = True
            except IntegrityError:
                # Potential race conditions may arise when multiple
                # celery workers concurrently write data to InfluxDB.
                # These simultaneous writes can result in the database
                # processing transactions from another "metric.save()"
                # call, potentially leading to IntegrityError exceptions.
                return cls._get_or_create(**kwargs)
        return metric, created

    @classmethod
    @cache_memoize(CACHE_TIMEOUT, key_generator_callable=get_metric_cache_key)
    def _get_metric(cls, *args, **kwargs):
        return cls.objects.get(**kwargs)

    @classmethod
    def invalidate_cache(cls, instance, *args, **kwargs):
        if kwargs.get('created', False):
            return
        cls._get_metric.invalidate(
            **{
                'name': instance.name,
                'key': instance.key,
                'content_type_id': instance.content_type_id,
                'object_id': instance.object_id,
                'configuration': instance.configuration,
                'main_tags': instance.main_tags,
            }
        )

    @property
    def codename(self):
        """Identifier stored in timeseries db."""
        return self._makekey(self.name)

    @property
    def config_dict(self):
        try:
            return get_metric_configuration()[self.configuration]
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
        """Produces a valid InfluxDB key from ``value``.

        Takes ``value`` as input argument and returs a valid InfluxDB key.
        """
        return clean_timeseries_data_key(value)

    @property
    def tags(self):
        tags = {}
        if self.content_type_id and self.object_id:
            tags.update(
                {
                    'content_type': self.content_type_key,
                    'object_id': str(self.object_id),
                }
            )
        if self.main_tags:
            tags.update(self.main_tags)
        if self.extra_tags:
            tags.update(self.extra_tags)
        return tags

    @staticmethod
    def _sort_dict(dict_):
        """Ensures the order of the keys in the dict is predictable."""
        if not isinstance(dict_, OrderedDict):
            return OrderedDict(sorted(dict_.items()))
        return dict_

    @property
    def content_type_key(self):
        try:
            content_type = ContentType.objects.get_for_id(self.content_type_id)
            return '.'.join(content_type.natural_key())
        except AttributeError:
            return None

    @property
    def alert_field(self):
        if self.field_name != self.config_dict['field_name']:
            return self.field_name
        return self.config_dict.get('alert_field', self.field_name)

    @property
    def alert_on_related_field(self):
        return self.alert_field in self.related_fields

    def _get_time(self, time):
        """If time is a string, it converts it to a datetime."""
        if isinstance(time, str):
            return parse_date(time)
        return time

    def _set_is_healthy(self, alert_settings, value):
        """Sets the value of "is_healthy" field when necessary.

        Executes only if "value" crosses the threshold defined in
        "alert_settings". Returns "True" if "is_healthy" field is changed.
        Otherwise, returns "None".

        This method does not take into account the alert settings
        tolerance, which is done by "_set_is_healthy_tolerant" method.
        """
        crossed = alert_settings._value_crossed(value)
        if (not crossed and self.is_healthy) or (crossed and self.is_healthy is False):
            return
        # problem: not within threshold limit
        elif crossed and self.is_healthy in [True, None]:
            self.is_healthy = False
        # ok: returned within threshold limit
        elif not crossed and self.is_healthy in [False, None]:
            self.is_healthy = True
        return True

    def _set_is_healthy_tolerant(
        self, alert_settings, value, time, retention_policy, send_alert
    ):
        """Sets the value of "is_tolerance_healthy" if necessary.

        Executes only if "value" crosses the threshold for more than the
        amount of seconds defined in the alert_settings "tolerance" field.
        It also sends the notification if required. Returns "None" if
        value of "is_healthy_tolerant" is unchanged. Returns "True" if it
        is the first metric write within threshold. Returns "False" in
        other cases.

        This method is similar to "_set_is_healthy" but it takes into
        account the alert settings tolerance so it's slightly different
        and more complex.
        """
        time = self._get_time(time)
        crossed = alert_settings._is_crossed_by(value, time, retention_policy)
        first_time = False
        # situation has not changed
        if (not crossed and self.is_healthy_tolerant) or (
            crossed and self.is_healthy_tolerant is False
        ):
            return
        # problem: not within threshold limit
        elif crossed and self.is_healthy_tolerant in [True, None]:
            if self.is_healthy_tolerant is None:
                first_time = True
            self.is_healthy_tolerant = False
            notification_type = f'{self.configuration}_problem'
        # ok: returned within threshold limit
        elif not crossed and self.is_healthy_tolerant is False:
            self.is_healthy_tolerant = True
            notification_type = f'{self.configuration}_recovery'
        # First metric write within threshold
        elif not crossed and self.is_healthy_tolerant is None:
            self.is_healthy_tolerant = True
            first_time = True

        # If we got to this point, it means we have to send an alert,
        # because the metric has been crossed for more than the
        # tolerated amount of time. There's one exception though:
        # if the device is new, its status will be unknown and the metric
        # will become healthy for the first time, in this case we do not need
        # to send an alert.
        if (
            not (first_time and self.is_healthy_tolerant)
            and alert_settings.is_active
            and send_alert
        ):
            self._notify_users(notification_type, alert_settings)
        return first_time

    def check_threshold(self, value, time=None, retention_policy=None, send_alert=True):
        """Checks if the threshold is crossed and notifies users accordingly"""
        try:
            alert_settings = self.alertsettings
        except ObjectDoesNotExist:
            return
        is_healthy_changed = self._set_is_healthy(alert_settings, value)
        tolerance_healthy_changed_first_time = self._set_is_healthy_tolerant(
            alert_settings, value, time, retention_policy, send_alert
        )
        is_healthy_tolerant_changed = tolerance_healthy_changed_first_time is not None
        # Do nothing if none of the fields changed.
        if not is_healthy_changed and not is_healthy_tolerant_changed:
            return
        update_fields = []
        if is_healthy_changed:
            update_fields.append('is_healthy')
        if is_healthy_tolerant_changed:
            update_fields.append('is_healthy_tolerant')
        self.save(update_fields=update_fields)
        threshold_crossed.send(
            sender=self.__class__,
            alert_settings=alert_settings,
            metric=self,
            target=self.content_object,
            first_time=tolerance_healthy_changed_first_time,
            tolerance_crossed=is_healthy_tolerant_changed,
        )

    def write(
        self,
        value,
        current=False,
        time=None,
        database=None,
        check=True,
        extra_values=None,
        retention_policy=None,
        send_alert=True,
        write=True,
    ):
        """write timeseries data"""
        values = {self.field_name: value}
        if extra_values and isinstance(extra_values, dict):
            for key in extra_values.keys():
                if not self.related_fields or key not in self.related_fields:
                    raise ValueError(f'"{key}" not defined in metric configuration')
            values.update(extra_values)
        signal_kwargs = dict(
            sender=self.__class__,
            metric=self,
            values=values,
            time=time,
            current=current,
        )
        pre_metric_write.send(**signal_kwargs)
        timestamp = time or timezone.now()
        if isinstance(timestamp, str):
            timestamp = parse_date(timestamp)
        options = dict(
            tags=self.tags,
            timestamp=timestamp.isoformat(),
            database=database,
            retention_policy=retention_policy,
            current=current,
        )
        # check can be disabled,
        # mostly for automated testing and debugging purposes
        if check:
            options['check_threshold_kwargs'] = {
                'value': value,
                'time': time,
                'retention_policy': retention_policy,
                'send_alert': send_alert,
            }
            options['metric'] = self

            # if alert_on_related_field then check threshold
            # on the related_field instead of field_name
            if self.alert_on_related_field:
                if not extra_values:
                    raise ValueError(
                        'write() missing keyword argument: "extra_values" required for alert on related field'
                    )
                if self.alert_field not in extra_values.keys():
                    raise ValueError(
                        f'"{key}" is not defined for alert_field in metric configuration'
                    )
                options['check_threshold_kwargs'].update(
                    {'value': extra_values[self.alert_field]}
                )
        if write:
            _timeseries_write(name=self.key, values=values, **options)
        return {'name': self.key, 'values': values, **options}

    @classmethod
    def batch_write(cls, raw_data):
        error_dict = {}
        write_data = []
        for metric, kwargs in raw_data:
            try:
                write_data.append(metric.write(**kwargs, write=False))
            except ValueError as error:
                error_dict[metric.key] = str(error)
        _timeseries_batch_write(write_data)
        if error_dict:
            raise ValueError(error_dict)

    def read(self, **kwargs):
        """reads timeseries data"""
        return timeseries_db.read(
            key=self.key, fields=self.field_name, tags=self.tags, **kwargs
        )

    def _notify_users(self, notification_type, alert_settings):
        """creates notifications for users"""
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
    GROUP_MAP = {'1d': '10m', '3d': '20m', '7d': '1h', '30d': '24h', '365d': '7d'}
    DEFAULT_TIME = DEFAULT_CHART_TIME

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
    def fill(self):
        return self.config_dict.get('fill')

    @property
    def xaxis(self):
        return self.config_dict.get('xaxis', {})

    @property
    def yaxis(self):
        return self.config_dict.get('yaxis', {})

    @property
    def label(self):
        return self.config_dict.get('label') or self.title

    @property
    def trace_type(self):
        return self.config_dict.get('trace_type', {})

    @property
    def trace_order(self):
        return self.config_dict.get('trace_order', [])

    @property
    def trace_labels(self):
        return self.config_dict.get('trace_labels', {})

    @property
    def calculate_total(self):
        return self.config_dict.get('calculate_total', False)

    @property
    def connect_points(self):
        return self.config_dict.get('connect_points', False)

    @property
    def description(self):
        return self.config_dict['description'].format(
            metric=self.metric, **self.metric.tags
        )

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
    def summary_query(self):
        query = self.config_dict.get('summary_query', None)
        if query:
            return query[timeseries_db.backend_name]

    @property
    def top_fields(self):
        return self.config_dict.get('top_fields', None)

    @property
    def _default_query(self):
        q = default_chart_query[0]
        if self.metric.object_id:
            q += default_chart_query[1]
        return q

    @classmethod
    def _get_group_map(cls, time=None):
        """Returns group map.

        Returns the chart group map for the specified days, otherwise the
        default Chart.GROUP_MAP is returned.
        """
        if (
            not time
            or time in cls.GROUP_MAP.keys()
            or not isinstance(time, str)
            or time[-1] != 'd'
        ):
            return cls.GROUP_MAP
        group = '10m'
        days = int(time.split('d')[0])
        # Use copy of class variable to avoid unpredictable results
        custom_group_map = cls.GROUP_MAP.copy()
        # custom grouping between 1 to 2 days
        if days > 0 and days < 3:
            group = '10m'
        # custom grouping between 3 to 6 days (base 5)
        elif days >= 3 and days < 7:
            group = str(5 * round(((days / 3) * 20) / 5)) + 'm'
        # custom grouping between 8 to 27 days
        elif days > 7 and days < 28:
            group = str(round(days / 7)) + 'h'
        # custom grouping between 1 month to 7 month
        elif days >= 30 and days <= 210:
            group = '1d'
        # custom grouping between 7 month to 1 year
        elif days > 210 and days <= 365:
            group = '7d'
        custom_group_map.update({time: group})
        return custom_group_map

    def get_query(
        self,
        time=DEFAULT_TIME,
        summary=False,
        fields=None,
        query=None,
        timezone=settings.TIME_ZONE,
        start_date=None,
        end_date=None,
        additional_params=None,
    ):
        query = query or self.query
        if summary and self.summary_query:
            query = self.summary_query
        additional_params = additional_params or {}
        params = self._get_query_params(time, start_date, end_date)
        params.update(additional_params)
        params.update({'start_date': start_date, 'end_date': end_date})
        if not params.get('organization_id') and self.config_dict.get('__all__', False):
            params['organization_id'] = ['__all__']
        return timeseries_db.get_query(
            self.type,
            params,
            time,
            self._get_group_map(time),
            summary,
            fields,
            query,
            timezone,
        )

    def get_top_fields(self, number):
        """Returns the top fields.

        Returns list of top ``number`` of fields (highest sum) of a
        measurement in the specified time range (descending order).
        """
        q = self._default_query.replace('{field_name}', '{fields}')
        params = self._get_query_params(self.DEFAULT_TIME)
        return timeseries_db._get_top_fields(
            query=q,
            chart_type=self.type,
            group_map=self._get_group_map(params['days']),
            number=number,
            params=params,
            time=self.DEFAULT_TIME,
        )

    def _get_query_params(self, time, start_date=None, end_date=None):
        m = self.metric
        params = dict(
            field_name=m.field_name,
            key=m.key,
            time=self._get_time(time, start_date, end_date),
            days=time,
        )
        if m.object_id:
            params.update(
                {
                    'content_type': m.content_type_key,
                    'object_id': m.object_id,
                    **m.tags,
                }
            )
        for key, value in self.config_dict.get('query_default_param', {}).items():
            params.setdefault(key, value)
        return params

    @classmethod
    def _get_time(cls, time, start_date=None, end_date=None):
        if start_date and end_date:
            return start_date
        if not isinstance(time, str):
            return str(time)
        if time in cls._get_group_map(time).keys():
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
        start_date=None,
        end_date=None,
        additional_query_kwargs=None,
    ):
        additional_query_kwargs = additional_query_kwargs or {}
        traces = {}
        if x_axys:
            x = []
        try:
            query_kwargs = dict(
                time=time, timezone=timezone, start_date=start_date, end_date=end_date
            )
            query_kwargs.update(additional_query_kwargs)
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
            data.update(
                {
                    'unit': self.unit,
                    'trace_type': self.trace_type,
                    'trace_order': self.trace_order,
                    'calculate_total': self.calculate_total,
                    'connect_points': self.connect_points,
                    'colors': self.colors,
                }
            )
            return json.dumps(data, **kwargs, default=str)
        except KeyError as e:
            logger.warning(f'Got KeyError in Chart.json method: {e}')

    @staticmethod
    def _round(value, decimal_places):
        """Rounds value when necessary."""
        control = 1.0 / 10**decimal_places
        if value < control:
            decimal_places += 2
        return round(value, decimal_places)


class AbstractAlertSettings(TimeStampedEditableModel):
    _MINUTES_MAX = 60 * 24 * 7  # 7 days
    _MINUTES_HELP = (
        'for how many minutes should the threshold value be crossed before '
        'an alert is sent? A value of zero means the alert is sent immediately'
    )
    _ALERTSETTINGS_OPERATORS = (('<', _('less than')), ('>', _('greater than')))
    is_active = models.BooleanField(
        _('Alerts enabled'),
        default=True,
        help_text=_(
            'whether alerts are enabled for this metric, uncheck to '
            'disable this alert for this object and all users'
        ),
    )
    metric = models.OneToOneField(
        get_model_name('monitoring', 'Metric'), on_delete=models.CASCADE
    )
    custom_operator = models.CharField(
        _('operator'),
        max_length=1,
        choices=_ALERTSETTINGS_OPERATORS,
        null=True,
        blank=True,
    )
    custom_threshold = models.FloatField(
        _('threshold value'), help_text=_('threshold value'), blank=True, null=True
    )
    custom_tolerance = models.PositiveIntegerField(
        _('threshold tolerance'),
        validators=[MaxValueValidator(_MINUTES_MAX)],
        help_text=_(_MINUTES_HELP),
        blank=True,
        null=True,
    )

    class Meta:
        abstract = True
        verbose_name = _('Alert settings')
        verbose_name_plural = verbose_name
        permissions = (
            ('add_alertsettings_inline', 'Can add Alert settings inline'),
            ('change_alertsettings_inline', 'Can change Alert settings inline'),
            ('delete_alertsettings_inline', 'Can delete Alert settings inline'),
            ('view_alertsettings_inline', 'Can view Alert settings inline'),
        )

    @classmethod
    def invalidate_cache(cls, instance, *args, **kwargs):
        Metric = instance.metric._meta.model
        Metric.invalidate_cache(instance.metric)

    def full_clean(self, *args, **kwargs):
        if self.custom_threshold == self.config_dict['threshold']:
            self.custom_threshold = None
        if self.custom_tolerance == self.config_dict['tolerance']:
            self.custom_tolerance = None
        if self.custom_operator == self.config_dict['operator']:
            self.custom_operator = None
        return super().full_clean(*args, **kwargs)

    @property
    def config_dict(self):
        return self.metric.config_dict.get(
            'alert_settings', {'operator': '<', 'threshold': 1, 'tolerance': 0}
        )

    @property
    def threshold(self):
        if self.custom_threshold is None:
            return self.config_dict['threshold']
        return self.custom_threshold

    @property
    def tolerance(self):
        if self.custom_tolerance is None:
            return self.config_dict['tolerance']
        return self.custom_tolerance

    @property
    def operator(self):
        if self.custom_operator is None:
            return self.config_dict['operator']
        return self.custom_operator

    def _value_crossed(self, current_value):
        threshold_value = self.threshold
        method = '__gt__' if self.operator == '>' else '__lt__'
        if isinstance(current_value, int):
            current_value = float(current_value)
        return getattr(current_value, method)(threshold_value)

    def _time_crossed(self, time):
        threshold_time = timezone.now() - timedelta(minutes=self.tolerance)
        return time < threshold_time

    @property
    def _tolerance_search_range(self):
        """Returns an amount of minutes to search.

        Allows sufficient room for checking if the tolerance has been
        trepassed. Minimum 15 minutes, maximum self._MINUTES_MAX * 1.05.
        """
        minutes = self.tolerance * 2
        minutes = minutes if minutes > 15 else 15
        minutes = minutes if minutes <= self._MINUTES_MAX else self._MINUTES_MAX * 1.05
        return int(minutes)

    def _is_crossed_by(self, current_value, time=None, retention_policy=None):
        """Answers the following question:

        do current_value and time cross the threshold and trepass the
        tolerance?
        """
        value_crossed = self._value_crossed(current_value)
        if value_crossed is NotImplemented:
            raise ValueError('Supplied value type not suppported')
        # no tolerance specified, return immediately
        if self.tolerance == 0:
            return value_crossed
        # tolerance is set, we must go back in time
        # to ensure the threshold is trepassed for enough time
        # if alert field is supplied, retrieve such field when reading
        # so that we can let the system calculate the threshold on it
        extra_fields = []
        if self.metric.alert_on_related_field:
            extra_fields = [self.metric.alert_field]
        if time is None:
            # retrieves latest measurements, ordered by most recent first
            points = self.metric.read(
                since=f'{self._tolerance_search_range}m',
                limit=None,
                order='-time',
                retention_policy=retention_policy,
                extra_fields=extra_fields,
            )
            # store a list with the results
            results = [value_crossed]
            # loop on each measurement starting from the most recent
            for i, point in enumerate(points, 1):
                # skip the first point because it was just added before this
                # check started and its value coincides with ``current_value``
                if i <= 1:
                    continue
                utc_time = utc.localize(datetime.utcfromtimestamp(point['time']))
                # did this point cross the threshold? Append to result list
                results.append(self._value_crossed(point[self.metric.alert_field]))
                # tolerance is trepassed
                if self._time_crossed(utc_time):
                    # if the latest results are consistent, the metric being
                    # monitored is not flapping and we can confidently return
                    # wheter the value crosses the threshold or not
                    if len(set(results)) == 1:
                        return value_crossed
                    # otherwise, the results are flapping, the situation has not changed
                    # we will return a value that will not trigger changes
                    return not self.metric.is_healthy_tolerant
                # otherwise keep looking back
                continue
            # the search has not yielded any conclusion
            # return result based on the current value and time
            time = timezone.now()
        return self._time_crossed(time) and value_crossed
