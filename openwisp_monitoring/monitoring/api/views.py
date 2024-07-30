from cache_memoize import cache_memoize
from django.db.models import Q
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from swapper import load_model

from openwisp_users.api.mixins import ProtectedAPIMixin

from ...settings import CACHE_TIMEOUT
from ...views import MonitoringApiViewMixin
from ..configuration import DEFAULT_DASHBOARD_TRAFFIC_CHART

Chart = load_model('monitoring', 'Chart')
Metric = load_model('monitoring', 'Metric')
Organization = load_model('openwisp_users', 'Organization')
Location = load_model('geo', 'Location')
FloorPlan = load_model('geo', 'FloorPlan')


class DashboardTimeseriesView(ProtectedAPIMixin, MonitoringApiViewMixin, APIView):
    """Multi-tenant view that returns general monitoring charts for the admin dashboard.

    Allows filtering with organization slugs.
    """

    permission_classes = [IsAuthenticated]

    def _get_organizations(self):
        query_orgs = self.request.query_params.get('organization_slug', '')
        if query_orgs:
            query_orgs = query_orgs.split(',')
            org_ids = list(
                Organization.objects.filter(slug__in=query_orgs).values_list(
                    'id', flat=True
                )
            )
            if len(org_ids) != len(query_orgs):
                # Request query_params contains slugs of non-existing organization
                raise NotFound
            if self.request.user.is_superuser or all(
                [str(id) in self.request.user.organizations_managed for id in org_ids]
            ):
                return org_ids
            # Request query_params contains slugs for organizations that user
            # doesn't manage
            raise PermissionDenied
        else:
            if self.request.user.is_superuser:
                return []
            elif self.request.user.organizations_managed:
                return self.request.user.organizations_managed
            else:
                # The user does not manage any organization
                raise PermissionDenied

    def _get_interface(self):
        orgs = self._get_organizations()
        interfaces = []
        if len(orgs) == 1:
            interfaces = DEFAULT_DASHBOARD_TRAFFIC_CHART.get(str(orgs[0]), [])
        if not interfaces:
            interfaces = DEFAULT_DASHBOARD_TRAFFIC_CHART.get('__all__')
        return interfaces

    def _get_location_ids(self):
        location_ids = self.request.query_params.get('location_id', '')
        if location_ids:
            location_ids = location_ids.split(',')
            location_query = Q(id__in=location_ids)
            if not self.request.user.is_superuser:
                location_query &= Q(organization__in=self._get_organizations())
            location_orgs = Location.objects.filter(location_query).values_list(
                'organization_id', flat=True
            )
            if len(location_ids) != len(location_orgs):
                # Request query_params contains slugs of non-existing organization
                raise NotFound
            if self.request.user.is_superuser or all(
                [
                    str(id) in self.request.user.organizations_managed
                    for id in location_orgs
                ]
            ):
                return location_ids
            # Request query_params contains ids of location from organizations that user
            # doesn't manage
            raise PermissionDenied
        else:
            if (
                self.request.user.is_superuser
                or self.request.user.organizations_managed
            ):
                # Don't filter by location by default
                return []
            else:
                # The user does not manage any organization
                raise PermissionDenied

    def _get_floorplan_ids(self):
        floorplan_ids = self.request.query_params.get('floorplan_id', '')
        if floorplan_ids:
            floorplan_ids = floorplan_ids.split(',')
            floorplan_query = Q(id__in=floorplan_ids)
            if not self.request.user.is_superuser:
                locations = self._get_location_ids()
                if locations:
                    floorplan_query &= Q(location__in=locations)
                else:
                    orgs = self._get_organizations()
                    floorplan_query &= Q(location__organization__in=orgs)
            floorplan_count = FloorPlan.objects.filter(floorplan_query).count()
            if len(floorplan_ids) != floorplan_count:
                # Request query_params contains slugs of non-existing organization
                raise NotFound
            if (
                self.request.user.is_superuser
                or self.request.user.organizations_managed
            ):
                return floorplan_ids
            # Request query_params contains ids of floorplan from organizations that user
            # doesn't manage
            raise PermissionDenied
        else:
            if (
                self.request.user.is_superuser
                or self.request.user.organizations_managed
            ):
                # Don't filter by floorplan by default
                return []
            else:
                # The user does not manage any organization
                raise PermissionDenied

    def _get_chart_additional_query_kwargs(self, chart):
        additional_params = {
            'organization_id': self._get_organizations(),
            'location_id': self._get_location_ids(),
            'floorplan_id': self._get_floorplan_ids(),
        }
        if chart.configuration == 'general_traffic':
            additional_params['ifname'] = self._get_interface()
        return {'additional_params': additional_params}

    @cache_memoize(
        CACHE_TIMEOUT,
        key_generator_callable=lambda *args, **kwargs: 'ow-monitoring-dashboard-charts',
    )
    def _get_charts(self, request, *args, **kwargs):
        return Chart.objects.filter(
            metric__object_id=None, metric__content_type=None
        ).select_related('metric')

    @classmethod
    def invalidate_cache(cls, instance, *args, **kwargs):
        if isinstance(instance, Chart):
            if (
                instance.metric.object_id is not None
                or instance.metric.content_type is not None
            ):
                return
        elif isinstance(instance, Metric):
            if instance.object_id is not None or instance.content_type is not None:
                return
        cls._get_charts.invalidate()

    def _get_user_managed_orgs(self, request):
        """Return list of dictionary containing organization name and slug in select2 compatible format."""
        orgs = []
        qs = Organization.objects.only('slug', 'name')
        if not request.user.is_superuser:
            if len(request.user.organizations_managed) > 1:
                qs = qs.filter(pk__in=request.user.organizations_managed)
            else:
                return orgs
        for org in qs.iterator():
            orgs.append({'id': org.slug, 'text': org.name})
        if len(orgs) < 2:
            # Handles scenarios for superuser when the project has only
            # one organization.
            return []
        return orgs

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        if not request.GET.get('csv'):
            user_managed_orgs = self._get_user_managed_orgs(request)
            if user_managed_orgs:
                response.data['organizations'] = user_managed_orgs
        return response


dashboard_timeseries = DashboardTimeseriesView.as_view()
