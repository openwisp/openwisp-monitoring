from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.utils.translation import gettext_lazy as _

from .utils import is_monitoring_blocked


class MonitoringBlockedObjectFormMixin:
    """Rejects admin form submissions for blocked monitoring targets."""

    def clean(self):
        cleaned_data = super().clean()
        content_type = cleaned_data.get("content_type")
        object_id = cleaned_data.get("object_id")
        if content_type and object_id:
            try:
                obj = content_type.get_object_for_this_type(pk=object_id)
            except ObjectDoesNotExist:
                obj = None
            if is_monitoring_blocked(obj):
                raise ValidationError(
                    _("Monitoring is blocked for the selected object.")
                )
        return cleaned_data


class DisabledOrgReadOnlyMixin:
    """Makes objects of a disabled organization or a deactivated device
    read-only in the admin.

    Deletion stays allowed, consistently with
    ``openwisp_users.multitenancy.MultitenantAdminMixin``.
    """

    def _get_related_object(self, obj):
        """Walks ``content_object``/``metric`` down to the leaf object."""
        if obj is None:
            return None
        content_object = getattr(obj, "content_object", None)
        if content_object is not None:
            return content_object
        metric = getattr(obj, "metric", None)
        if metric is not None:
            return self._get_related_object(metric)
        return obj

    def has_change_permission(self, request, obj=None):
        perm = super().has_change_permission(request, obj)
        return perm and not is_monitoring_blocked(self._get_related_object(obj))


class DisabledOrgReadOnlyInlineMixin(DisabledOrgReadOnlyMixin):
    """Inline flavour: ``has_add_permission`` also receives the parent object."""

    def has_add_permission(self, request, obj=None):
        perm = super().has_add_permission(request, obj)
        return perm and not is_monitoring_blocked(self._get_related_object(obj))
