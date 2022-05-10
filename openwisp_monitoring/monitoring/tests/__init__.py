from datetime import timedelta

from django.utils.timezone import now
from swapper import load_model

from openwisp_users.tests.utils import TestOrganizationMixin

from ...db import timeseries_db
from ...db.backends import TIMESERIES_DB
from ..configuration import (
    register_chart,
    register_metric,
    unregister_chart,
    unregister_metric,
)

start_time = now()
ten_minutes_ago = start_time - timedelta(minutes=10)
Chart = load_model('monitoring', 'Chart')
Metric = load_model('monitoring', 'Metric')
AlertSettings = load_model('monitoring', 'AlertSettings')

default_message = (
    '{notification.actor.name} for device [{notification.target}]'
    '({notification.target_link}) {notification.verb}.'
)

test_notification = {
    'problem': {
        'verbose_name': 'Monitoring Alert',
        'verb': 'crossed the threshold',
        'level': 'warning',
        'email_subject': '[{site.name}] PROBLEM: {notification.actor.name} {notification.target}',
        'message': default_message,
    },
    'recovery': {
        'verbose_name': 'Monitoring Alert',
        'verb': 'returned within the threshold',
        'level': 'info',
        'email_subject': '[{site.name}] RECOVERY: {notification.actor.name} {notification.target}',
        'message': default_message,
    },
}

# these custom metric configurations are used for automated testing purposes
metrics = {
    'test_metric': {
        'name': 'dummy',
        'key': '{key}',
        'field_name': '{field_name}',
        'label': 'Test Metric',
        'notification': test_notification,
    },
    'top_fields_mean': {
        'name': 'top_fields_mean_test',
        'key': '{key}',
        'field_name': '{field_name}',
        'label': 'top fields mean test',
        'related_fields': ['google', 'facebook', 'reddit'],
    },
    'get_top_fields': {
        'name': 'get_top_fields_test',
        'key': '{key}',
        'field_name': '{field_name}',
        'label': 'get top fields test',
        'related_fields': ['http2', 'ssh', 'udp', 'spdy'],
    },
}

# this custom chart configuration is used for automated testing purposes
charts = {
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
    },
    'dummy': {
        'type': 'line',
        'title': 'Dummy chart',
        'description': 'Dummy chart for testing purposes.',
        'unit': 'candies',
        'order': 999,
        'query': None,
    },
    'bad_test': {
        'type': 'line',
        'title': 'Bugged chart for testing purposes',
        'description': 'Bugged chart for testing purposes.',
        'unit': 'bugs',
        'order': 999,
        'query': {'influxdb': "BAD"},
    },
    'default': {
        'type': 'line',
        'title': 'Default query for testing purposes',
        'description': 'Default query for testing purposes',
        'unit': 'n.',
        'order': 999,
        'query': {
            'influxdb': (
                "SELECT {field_name} FROM {key} WHERE time >= '{time}' AND "
                "content_type = '{content_type}' AND object_id = '{object_id}'"
            )
        },
    },
    'multiple_test': {
        'type': 'line',
        'title': 'Multiple test',
        'description': 'For testing purposes',
        'unit': 'n.',
        'order': 999,
        'query': {
            'influxdb': (
                "SELECT {field_name}, value2 FROM {key} WHERE time >= '{time}' AND "
                "content_type = '{content_type}' AND object_id = '{object_id}'"
            )
        },
    },
    'mean_test': {
        'type': 'line',
        'title': 'Mean test',
        'description': 'For testing purposes',
        'unit': 'n.',
        'order': 999,
        'query': {
            'influxdb': (
                "SELECT MEAN({field_name}) AS {field_name} FROM {key} WHERE time >= '{time}' AND "
                "content_type = '{content_type}' AND object_id = '{object_id}'"
            )
        },
    },
    'sum_test': {
        'type': 'line',
        'title': 'Sum test',
        'description': 'For testing purposes',
        'unit': 'n.',
        'order': 999,
        'query': {
            'influxdb': (
                "SELECT SUM({field_name}) AS {field_name} FROM {key} WHERE time >= '{time}' AND "
                "content_type = '{content_type}' AND object_id = '{object_id}'"
            )
        },
    },
    'top_fields_mean': {
        'type': 'histogram',
        'title': 'Top fields mean test',
        'description': 'For testing purposes',
        'top_fields': 2,
        'order': 999,
        'query': {
            'influxdb': (
                "SELECT {fields|MEAN} FROM {key} "
                "WHERE time >= '{time}' AND content_type = "
                "'{content_type}' AND object_id = '{object_id}'"
            )
        },
    },
}


class TestMonitoringMixin(TestOrganizationMixin):
    ORIGINAL_DB = TIMESERIES_DB['NAME']
    TEST_DB = f'{ORIGINAL_DB}_test'

    @classmethod
    def setUpClass(cls):
        # By default timeseries_db.db shall connect to the database
        # defined in settings when apps are loaded. We don't want that while testing
        timeseries_db.db_name = cls.TEST_DB
        del timeseries_db.db
        timeseries_db.create_database()
        for key, value in metrics.items():
            register_metric(key, value)
        for key, value in charts.items():
            register_chart(key, value)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        timeseries_db.drop_database()
        for metric_name in metrics.keys():
            unregister_metric(metric_name)
        for key in charts.keys():
            unregister_chart(key)
        super().tearDownClass()

    def tearDown(self):
        timeseries_db.delete_metric_data()
        super().tearDown()

    def _create_general_metric(self, **kwargs):
        opts = {
            'name': 'test_metric',
            'is_healthy': True,  # backward compatibility with old tests
            'is_healthy_tolerant': True,  # backward compatibility with old tests
            'configuration': 'test_metric',
        }
        opts.update(kwargs)
        m = Metric(**opts)
        m.full_clean()
        m.save()
        return m

    def _create_object_metric(self, **kwargs):
        opts = kwargs.copy()
        if 'content_object' not in opts:
            opts['content_object'] = self._create_user()
        if 'is_healthy' not in kwargs:
            kwargs['is_healthy'] = True  # backward compatibility with old tests
        return self._create_general_metric(**opts)

    def _create_alert_settings(self, **kwargs):
        alert_s = AlertSettings(**kwargs)
        alert_s.full_clean()
        alert_s.save()
        return alert_s

    def _create_chart(self, metric=None, test_data=True, configuration='dummy'):
        m = metric or self._create_object_metric()
        if test_data:
            m.write(3, time=now() - timedelta(days=2))
            m.write(6, time=now() - timedelta(days=1))
            m.write(9, time=now())
        c = Chart(metric=m, configuration=configuration)
        c.full_clean()
        c.save()
        return c

    def _data(self):
        return {
            'type': 'DeviceMonitoring',
            'general': {'local_time': 1589026500, 'uptime': 8003},
            'resources': {
                'cpus': 1,
                'memory': {
                    'total': 249774080,
                    'shared': 86016,
                    'free': 224497664,
                    'cached': 6774784,
                    'available': 223397664,
                    'buffered': 974848,
                },
                'load': [0, 0, 0],
                'disk': [
                    {
                        'used_bytes': 18792,
                        'available_bytes': 233984,
                        'filesystem': '/dev/root',
                        'mount_point': '/',
                        'used_percent': 7,
                        'size_bytes': 258016,
                    },
                    {
                        'used_bytes': 3872,
                        'available_bytes': 11916,
                        'filesystem': '/dev/sda1',
                        'mount_point': '/boot',
                        'used_percent': 25,
                        'size_bytes': 16112,
                    },
                ],
                'swap': {'free': 0, 'total': 0},
            },
            'interfaces': [
                {
                    'name': 'wlan0',
                    'type': 'wireless',
                    'up': True,
                    'mac': '44:d1:fa:4b:38:43',
                    'txqueuelen': 1000,
                    'multicast': True,
                    'mtu': 1500,
                    'statistics': {
                        'rx_bytes': 324,
                        'tx_bytes': 145,
                        'collisions': 0,
                        'multicast': 0,
                        'rx_dropped': 0,
                        'tx_dropped': 0,
                    },
                    'wireless': {
                        'frequency': 2437,
                        'mode': 'access_point',
                        'signal': -29,
                        'tx_power': 6,
                        'channel': 6,
                        'ssid': 'testnet',
                        'noise': -95,
                        'country': 'US',
                        'clients': [
                            {
                                'mac': '00:ee:ad:34:f5:3b',
                                'wps': False,
                                'wds': False,
                                'ht': True,
                                'preauth': False,
                                'assoc': True,
                                'authorized': True,
                                'vht': False,
                                'wmm': True,
                                'aid': 1,
                                'mfp': False,
                                'auth': True,
                                'signature': 'test_signature',
                            }
                        ],
                    },
                },
                {
                    'name': 'wlan1',
                    'type': 'wireless',
                    'up': True,
                    'mac': '44:d1:fa:4b:38:44',
                    'txqueuelen': 1000,
                    'multicast': True,
                    'mtu': 1500,
                    'statistics': {
                        'rx_bytes': 2275,
                        'tx_bytes': 826,
                        'collisions': 0,
                        'multicast': 0,
                        'rx_dropped': 0,
                        'tx_dropped': 0,
                    },
                    'wireless': {
                        'frequency': 2437,
                        'mode': 'access_point',
                        'signal': -29,
                        'tx_power': 6,
                        'channel': 6,
                        'ssid': 'testnet',
                        'noise': -95,
                        'country': 'US',
                        'clients': [
                            {
                                'mac': 'b0:e1:7e:30:16:44',
                                'wps': False,
                                'wds': False,
                                'ht': True,
                                'preauth': False,
                                'assoc': True,
                                'authorized': True,
                                'vht': False,
                                'wmm': True,
                                'aid': 1,
                                'mfp': False,
                                'auth': True,
                                'signature': 'test_signature',
                            },
                            {
                                'mac': 'c0:ee:fb:34:f5:4b',
                                'wps': False,
                                'wds': False,
                                'ht': True,
                                'preauth': False,
                                'assoc': True,
                                'authorized': True,
                                'vht': False,
                                'wmm': True,
                                'aid': 1,
                                'mfp': False,
                                'auth': True,
                                'signature': 'test_signature',
                            },
                        ],
                    },
                },
            ],
        }
