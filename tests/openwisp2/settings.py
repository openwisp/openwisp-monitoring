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

EXTENDED_APPS = (
    'django_netjsonconfig',
    'django_x509',
    'django_loci',
)

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

INFLUXDB_USER = 'openwisp'
INFLUXDB_PASSWORD = 'openwisp'
INFLUXDB_DATABASE = 'openwisp2'

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

# this custom chart configuration is used for automated testing purposes
OPENWISP_MONITORING_CHARTS = {
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

# avoid slowing down the test suite with mac vendor lookups
if TESTING:
    OPENWISP_MONITORING_MAC_VENDOR_DETECTION = False

LOGGING = {
    'version': 1,
    'filters': {'require_debug_true': {'()': 'django.utils.log.RequireDebugTrue',}},
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'filters': ['require_debug_true'],
            'class': 'logging.StreamHandler',
        }
    },
    'loggers': {
        'py.warnings': {'handlers': ['console'],},
        'celery': {'handlers': ['console'], 'level': 'DEBUG',},
        'celery.task': {'handlers': ['console'], 'level': 'DEBUG',},
    },
}

# local settings must be imported before test runner otherwise they'll be ignored
try:
    from openwisp2.local_settings import *
except ImportError:
    pass
