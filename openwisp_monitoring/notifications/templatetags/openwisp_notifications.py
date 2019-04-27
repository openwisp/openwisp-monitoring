# -*- coding: utf-8 -*-
from distutils.version import StrictVersion

import swapper
from django import get_version
from django.core.cache import cache
from django.template import Library
from django.utils.html import format_html
from notifications.templatetags.notifications_tags import notifications_unread

Notification = swapper.load_model('notifications', 'Notification')

register = Library()


def get_notifications_count(context):
    user_pk = context['user'].is_authenticated and context['user'].pk
    cache_key = Notification.COUNT_CACHE_KEY.format(user_pk)
    count = cache.get(cache_key)
    if count is None:
        count = notifications_unread(context)
        cache.set(cache_key, count)
    return count


def unread_notifications(context):
    count = get_notifications_count(context)
    output = ''
    if count:
        output = '<span>{0}</span>'
        output = format_html(output.format(count))
    return output


if StrictVersion(get_version()) >= StrictVersion('2.0'):
    register.simple_tag(takes_context=True)(unread_notifications)
else:
    register.assignment_tag(takes_context=True)(notifications_unread)
