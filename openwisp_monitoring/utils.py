from asgiref.sync import sync_to_async
from django.apps import apps
from django.db import transaction
from swapper import is_swapped, split

try:
    from django.core.exceptions import SynchronousOnlyOperation
except ImportError:  # pragma: nocover

    class SynchronousOnlyOperation(Exception):
        pass


def transaction_on_commit(func):
    with transaction.atomic():
        transaction.on_commit(func)


def load_model_patched(app_label, model, require_ready=True):
    """
    TODO: remove if https://github.com/wq/django-swappable-models/pull/23 gets merged
    """
    swapped = is_swapped(app_label, model)
    if swapped:
        app_label, model = split(swapped)
    return apps.get_model(app_label, model, require_ready=require_ready)


def fix_async(func):
    """
    Runs function through sync_to_async if needed
    """
    try:
        return func()
    except SynchronousOnlyOperation:  # pragma: nocover
        return sync_to_async(func, thread_sensitive=True)
