import os
import sys
from datetime import timedelta

from celery.schedules import crontab

TESTING = 'test' in sys.argv
SHELL = 'shell' in sys.argv or 'shell_plus' in sys.argv
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DEBUG = True

ALLOWED_HOSTS = ['*']
# required by openwisp-notifications
INTERNAL_IPS = ['127.0.0.1']

DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.spatialite',
        'NAME': 'openwisp-monitoring.db',
    }
}

TIMESERIES_DATABASE = {
    'BACKEND': 'openwisp_monitoring.db.backends.influxdb',
    'USER': 'openwisp',
    'PASSWORD': 'openwisp',
    'NAME': 'openwisp2',
    'HOST': os.getenv('INFLUXDB_HOST', 'localhost'),
    'PORT': '8086',
}

SECRET_KEY = 'fn)t*+$)ugeyip6-#txyy$5wf2ervc0d2n#h)qb)y5@ly$t*@w'

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.gis',
    # all-auth
    'django.contrib.sites',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'django_extensions',
    'django_filters',
    # openwisp2 modules
    'openwisp_controller.config',
    'openwisp_controller.connection',
    'openwisp_controller.pki',
    'openwisp_controller.geo',
    'openwisp_users',
    'openwisp_ipam',
    # monitoring
    'openwisp_monitoring.monitoring',
    'openwisp_monitoring.device',
    'openwisp_monitoring.check',
    'nested_admin',
    # notifications
    'openwisp_notifications',
    # admin
    # openwisp2 admin theme
    # (must be loaded here)
    'openwisp_utils.admin_theme',
    'admin_auto_filters',
    'django.contrib.admin',
    'django.forms',
    # other dependencies
    'sortedm2m',
    'reversion',
    'leaflet',
    'flat_json_widget',
    # rest framework
    'rest_framework',
    'rest_framework.authtoken',
    'rest_framework_gis',
    'drf_yasg',
    # channels
    'channels',
    'import_export',
]

EXTENDED_APPS = ['django_x509', 'django_loci']

AUTH_USER_MODEL = 'openwisp_users.User'
SITE_ID = 1

STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'openwisp_utils.staticfiles.DependencyFinder',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'openwisp2.urls'

TIME_ZONE = 'Europe/Rome'
LANGUAGE_CODE = 'en-gb'
USE_TZ = True
USE_I18N = False
USE_L10N = False
STATIC_URL = '/static/'
MEDIA_URL = '/media/'
MEDIA_ROOT = '{0}/media/'.format(BASE_DIR)

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(os.path.dirname(BASE_DIR), 'templates')],
        'OPTIONS': {
            'loaders': [
                'django.template.loaders.filesystem.Loader',
                'django.template.loaders.app_directories.Loader',
                'openwisp_utils.loaders.DependencyLoader',
            ],
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'openwisp_utils.admin_theme.context_processor.menu_groups',
                'openwisp_utils.admin_theme.context_processor.admin_theme_settings',
                'openwisp_notifications.context_processors.notification_api_settings',
            ],
        },
    }
]

FORM_RENDERER = 'django.forms.renderers.TemplatesSetting'

EMAIL_PORT = '1025'  # for testing purposes
LOGIN_REDIRECT_URL = 'admin:index'
ACCOUNT_LOGOUT_REDIRECT_URL = LOGIN_REDIRECT_URL

# during development only
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

OPENWISP_MONITORING_MANAGEMENT_IP_ONLY = False

redis_host = os.getenv('REDIS_HOST', 'localhost')
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f'redis://{redis_host}/0',
        'OPTIONS': {'CLIENT_CLASS': 'django_redis.client.DefaultClient'},
    }
}

SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'

if not TESTING:
    CELERY_BROKER_URL = f'redis://{redis_host}/1'
else:
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True
    CELERY_BROKER_URL = 'memory://'

# Celery TIME_ZONE should be equal to django TIME_ZONE
# In order to schedule run_iperf3_checks on the correct time intervals
CELERY_TIMEZONE = TIME_ZONE

CELERY_BEAT_SCHEDULE = {
    'run_checks': {
        'task': 'openwisp_monitoring.check.tasks.run_checks',
        # Executes only ping & config check every 5 min
        'schedule': timedelta(minutes=5),
        'args': (
            [  # Checks path
                'openwisp_monitoring.check.classes.Ping',
                'openwisp_monitoring.check.classes.ConfigApplied',
            ],
        ),
        'relative': True,
    },
    'run_iperf3_checks': {
        'task': 'openwisp_monitoring.check.tasks.run_checks',
        # https://docs.celeryq.dev/en/latest/userguide/periodic-tasks.html#crontab-schedules
        # Executes only iperf3 check every 5 mins from 00:00 AM to 6:00 AM (night)
        'schedule': crontab(minute='*/5', hour='0-6'),
        'args': (['openwisp_monitoring.check.classes.Iperf3'],),
        'relative': True,
    },
}

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
CELERY_EMAIL_BACKEND = EMAIL_BACKEND

ASGI_APPLICATION = 'openwisp2.routing.application'

if TESTING:
    CHANNEL_LAYERS = {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}}
else:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {'hosts': [f'redis://{redis_host}/7']},
        }
    }

# avoid slowing down the test suite with mac vendor lookups
if TESTING:
    OPENWISP_MONITORING_MAC_VENDOR_DETECTION = False
    OPENWISP_MONITORING_API_URLCONF = 'openwisp_monitoring.urls'
    OPENWISP_MONITORING_API_BASEURL = 'http://testserver'
    # for testing AUTO_IPERF3
    OPENWISP_MONITORING_AUTO_IPERF3 = True

# Temporarily added to identify slow tests
TEST_RUNNER = 'openwisp_utils.tests.TimeLoggingTestRunner'

LEAFLET_CONFIG = {'RESET_VIEW': False}

LOGGING = {
    'version': 1,
    'filters': {'require_debug_true': {'()': 'django.utils.log.RequireDebugTrue'}},
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'filters': ['require_debug_true'],
            'class': 'logging.StreamHandler',
        }
    },
    'loggers': {
        '': {
            # this sets root level logger to log debug and higher level
            # logs to console. All other loggers inherit settings from
            # root level logger.
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django': {
            'handlers': ['console'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
        'py.warnings': {'handlers': ['console'], 'propagate': False},
        'celery': {'handlers': ['console'], 'level': 'DEBUG'},
        'celery.task': {'handlers': ['console'], 'level': 'DEBUG'},
    },
}

if not TESTING and SHELL:
    LOGGING.update(
        {
            'loggers': {
                'django.db.backends': {
                    'level': 'DEBUG',
                    'handlers': ['console'],
                    'propagate': False,
                },
            }
        }
    )

if os.environ.get('SAMPLE_APP', False):
    for app in [
        'openwisp_monitoring.monitoring',
        'openwisp_monitoring.check',
        'openwisp_monitoring.device',
    ]:
        INSTALLED_APPS.remove(app)
        EXTENDED_APPS.append(app)
    INSTALLED_APPS.append('openwisp2.sample_monitoring')
    INSTALLED_APPS.append('openwisp2.sample_check')
    INSTALLED_APPS.append('openwisp2.sample_device_monitoring')
    CHECK_CHECK_MODEL = 'sample_check.Check'
    MONITORING_CHART_MODEL = 'sample_monitoring.Chart'
    MONITORING_METRIC_MODEL = 'sample_monitoring.Metric'
    MONITORING_ALERTSETTINGS_MODEL = 'sample_monitoring.AlertSettings'
    DEVICE_MONITORING_WIFICLIENT_MODEL = 'sample_device_monitoring.WifiClient'
    DEVICE_MONITORING_WIFISESSION_MODEL = 'sample_device_monitoring.WifiSession'
    DEVICE_MONITORING_DEVICEDATA_MODEL = 'sample_device_monitoring.DeviceData'
    DEVICE_MONITORING_DEVICEMONITORING_MODEL = (
        'sample_device_monitoring.DeviceMonitoring'
    )
    # Celery auto detects tasks only from INSTALLED_APPS
    CELERY_IMPORTS = ('openwisp_monitoring.device.tasks',)

# local settings must be imported before test runner otherwise they'll be ignored
try:
    from openwisp2.local_settings import *
except ImportError:
    pass
