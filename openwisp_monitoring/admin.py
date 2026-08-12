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

    def _is_write_blocked(self, obj):
        related = self._get_related_object(obj)
        if related is None:
            return False
        if hasattr(related, "is_deactivated") and related.is_deactivated():
            return True
        organization = getattr(related, "organization", None)
        return organization is not None and not organization.is_active

    def has_change_permission(self, request, obj=None):
        perm = super().has_change_permission(request, obj)
        return perm and not self._is_write_blocked(obj)


class DisabledOrgReadOnlyInlineMixin(DisabledOrgReadOnlyMixin):
    """Inline flavour: ``has_add_permission`` also receives the parent object."""

    def has_add_permission(self, request, obj=None):
        perm = super().has_add_permission(request, obj)
        return perm and not self._is_write_blocked(obj)
