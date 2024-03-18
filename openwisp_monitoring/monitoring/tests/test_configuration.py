from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase
from django.utils.translation import gettext_lazy as _

from .. import settings as app_settings
from ..configuration import (
    DEFAULT_METRICS,
    get_metric_configuration,
    get_metric_configuration_choices,
    register_metric,
    unregister_metric,
)
from . import TestMonitoringMixin


class TestConfiguration(TestMonitoringMixin, TestCase):
    def _get_new_metric(self):
        return {
            'label': _('Histogram'),
            'name': 'Histogram',
            'key': 'histogram',
            'field_name': 'value',
            'charts': {
                'histogram': {
                    'type': 'histogram',
                    'title': 'Histogram',
                    'description': 'Histogram',
                    'top_fields': 2,
                    'order': 999,
                    'query': {
                        'influxdb': (
                            "SELECT {fields|SUM|/ 1} FROM {key} "
                            "WHERE time >= '{time}' AND content_type = "
                            "'{content_type}' AND object_id = '{object_id}'"
                        )
                    },
                }
            },
        }

    def test_register_invalid_metric_config(self):
        with self.subTest('Test Invalid Metric name'):
            with self.assertRaisesMessage(
                ImproperlyConfigured, 'Metric configuration name should be type "str".'
            ):
                register_metric(list(), {})
        with self.subTest('Test Invalid Metric Configuration'):
            with self.assertRaisesMessage(
                ImproperlyConfigured, 'Metric configuration should be type "dict".'
            ):
                register_metric('dummy_test', list())

    def test_unregister_invalid_metric_config(self):
        with self.subTest('Test invalid metric name'):
            with self.assertRaisesMessage(
                ImproperlyConfigured, 'Metric configuration name should be type "str".'
            ):
                unregister_metric(list())
        with self.subTest('Test unregister unregistered metric configuration'):
            with self.assertRaisesMessage(
                ImproperlyConfigured, 'No such Chart configuation "invalid".'
            ):
                unregister_metric('invalid')

    def test_register_duplicate_metric(self):
        m = self._create_general_metric()
        metric_config = m.config_dict
        with self.assertRaisesMessage(
            ImproperlyConfigured,
            f'{m.configuration} is an already registered Metric Configuration.',
        ):
            register_metric(m.configuration, metric_config)

    @patch.dict(DEFAULT_METRICS)
    def test_register_metric_configuration(self):
        metric_config = self._get_new_metric()
        register_metric('histogram', metric_config)
        self.assertIn(metric_config, get_metric_configuration().values())
        self.assertIn(('histogram', 'Histogram'), get_metric_configuration_choices())
        unregister_metric('histogram')

    @patch.dict(DEFAULT_METRICS)
    @patch.object(
        app_settings,
        'ADDITIONAL_METRICS',
        {
            'histogram': {
                'partial': True,
                'name': 'Partial Updated',
                'charts': {
                    'histogram': {
                        'title': 'Partial Updated',
                    }
                },
            }
        },
    )
    def test_overriding_registered_metric_configuration(self):
        metric_config = self._get_new_metric()
        register_metric('histogram', metric_config)
        metrics = get_metric_configuration()
        self.assertIn('histogram', metrics.keys())
        self.assertEqual(metrics['histogram']['name'], 'Partial Updated')
        self.assertEqual(
            metrics['histogram']['charts']['histogram']['title'], 'Partial Updated'
        )
