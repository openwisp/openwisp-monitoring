from __future__ import absolute_import, unicode_literals

import os

from celery import Celery
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'openwisp2.settings')

app = Celery('openwisp2')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
app.config_from_object('django.conf:settings', namespace='CELERY')

# don't ask me why this needs to be done
# but without it celery-beat won't work
# TODO: fixme
if hasattr(settings, 'CELERYBEAT_SCHEDULE'):
    app.conf.CELERYBEAT_SCHEDULE = settings.CELERYBEAT_SCHEDULE
