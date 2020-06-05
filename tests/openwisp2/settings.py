import os
import sys
from datetime import timedelta

TESTING = 'test' in sys.argv
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DEBUG = True

ALLOWED_HOSTS = ['*']

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
    'HOST': 'localhost',
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
    # openwisp2 admin theme
    # (must be loaded here)
    'openwisp_utils.admin_theme',
    # all-auth
    'django.contrib.sites',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'django_extensions',
    # openwisp2 modules
    'openwisp_controller.config',
    'openwisp_controller.connection',
    'openwisp_controller.pki',
    'openwisp_controller.geo',
    'openwisp_users',
    # monitoring
    'openwisp_monitoring.notifications',
    'openwisp_monitoring.monitoring',
    'openwisp_monitoring.device',
    'openwisp_monitoring.check',
    # notifications
    'openwisp_notifications',
    # admin
    'django.contrib.admin',
    'django.forms',
    # other dependencies
    'sortedm2m',
    'reversion',
    'leaflet',
    # rest framework
    'rest_framework',
    'rest_framework_gis',
    # channels
    'channels',
]

EXTENDED_APPS = [
    'django_netjsonconfig',
    'django_x509',
    'django_loci',
]

AUTH_USER_MODEL = 'openwisp_users.User'
SITE_ID = '1'

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

ASGI_APPLICATION = 'openwisp_controller.geo.channels.routing.channel_routing'
CHANNEL_LAYERS = {
    'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'},
}

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
                'apptemplates.Loader',
                'django.template.loaders.filesystem.Loader',
                'django.template.loaders.app_directories.Loader',
                'openwisp_utils.loaders.DependencyLoader',
            ],
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'openwisp_utils.admin_theme.context_processor.menu_items',
                'openwisp_utils.admin_theme.context_processor.admin_theme_settings',
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

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://localhost/0',
        'OPTIONS': {'CLIENT_CLASS': 'django_redis.client.DefaultClient',},
    }
}

SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'

if not TESTING:
    CELERY_BROKER_URL = 'redis://localhost/1'
else:
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True
    CELERY_BROKER_URL = 'memory://'

CELERY_BEAT_SCHEDULE = {
    'run_checks': {
        'task': 'openwisp_monitoring.check.tasks.run_checks',
        'schedule': timedelta(minutes=5),
        'args': None,
        'relative': True,
    },
}

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
CELERY_EMAIL_BACKEND = EMAIL_BACKEND

# these custom metric configurations are used for automated testing purposes
if TESTING:
    OPENWISP_MONITORING_METRICS = {
        'test_metric': {
            'name': 'dummy',
            'key': '{key}',
            'field_name': '{field_name}',
            'label': 'Test Metric',
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

# avoid slowing down the test suite with mac vendor lookups
if TESTING:
    OPENWISP_MONITORING_MAC_VENDOR_DETECTION = False

# Temporarily added to identify slow tests
TEST_RUNNER = 'openwisp_utils.tests.TimeLoggingTestRunner'

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

if not TESTING:
    LOGGING.update({'root': {'level': 'INFO', 'handlers': ['console']}})

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
