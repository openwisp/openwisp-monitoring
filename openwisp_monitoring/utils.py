from django.apps import apps
from django.db import transaction
from swapper import is_swapped, split


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
