import logging
from collections import OrderedDict

from django.conf import settings
from django.http import HttpResponse
from pytz import timezone as tz
from pytz.exceptions import UnknownTimeZoneError
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView
from swapper import load_model

from ...monitoring.exceptions import InvalidChartConfigException
from ..configuration import DEFAULT_DASHBOARD_TRAFFIC_CHART

logger = logging.getLogger(__name__)
Chart = load_model('monitoring', 'Chart')
Metric = load_model('monitoring', 'Metric')
Organization = load_model('openwisp_users', 'Organization')


class DashboardTimeseriesView(APIView):
    def _get_organizations(self):
        query_orgs = self.request.query_params.get('organization_slug', '')
        if query_orgs:
            query_orgs = query_orgs.split(',')
            org_ids = Organization.objects.filter(slug__in=query_orgs).values_list(
                'id', flat=True
            )
            if len(org_ids) != len(query_orgs):
                raise NotFound
            if self.request.user.is_superuser or all(
                [str(id) in self.request.user.organizations_managed for id in org_ids]
            ):
                return org_ids
            else:
                raise PermissionDenied
        else:
            if self.request.user.is_superuser:
                return []
            elif self.request.user.organizations_managed:
                return self.request.user.organizations_managed
            else:
                raise PermissionDenied

    def _get_query_clause(self, field, items):
        if not items:
            return ''
        lookup = []
        for item in items:
            lookup.append(f"{field} = '{item}'")
        return 'AND ({lookup})'.format(lookup=' OR '.join(lookup))

    def _get_organization_lookup(self):
        orgs = self._get_organizations()
        return self._get_query_clause('organization_id', orgs)

    def _get_ifname_lookup(self):
        orgs = self._get_organizations()
        interfaces = []
        if len(orgs) == 1:
            org_slug = self.request.GET.get(
                'organization_slug', Organization.objects.get(id=orgs[0]).slug
            )
            interfaces = DEFAULT_DASHBOARD_TRAFFIC_CHART.get(org_slug, [])
        if not interfaces:
            interfaces = DEFAULT_DASHBOARD_TRAFFIC_CHART.get('__all__')
        return self._get_query_clause('ifname', interfaces)

    def _get_chart_additional_query_kwargs(self, chart):
        org_lookup = self._get_organization_lookup()
        additional_params = {
            'organization_lookup': org_lookup,
        }
        if chart.configuration == 'general_traffic':
            additional_params['ifname_lookup'] = self._get_ifname_lookup()
        return {'additional_params': additional_params}

    def get(self, request):
        org_lookup = self._get_organization_lookup()
        charts = Chart.objects.filter(
            metric__object_id=None, metric__content_type=None
        ).select_related('metric')
        time = request.query_params.get('time', Chart.DEFAULT_TIME)
        if time not in Chart.GROUP_MAP.keys():
            return Response({'detail': 'Time range not supported'}, status=400)
        # try to read timezone
        timezone = request.query_params.get('timezone', settings.TIME_ZONE)
        try:
            tz(timezone)
        except UnknownTimeZoneError:
            return Response('Unkown Time Zone', status=400)
        # prepare response data
        data = self._get_charts_data(charts, time, timezone, org_lookup)
        # csv export has a different response
        if request.query_params.get('csv'):
            response = HttpResponse(self._get_csv(data), content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename=data.csv'
            return response
        return Response(data)

    def _get_charts_data(self, charts, time, timezone, org_lookup):
        chart_map = {}
        x_axys = True
        data = OrderedDict({'charts': []})
        for chart in charts:
            # prepare chart dict
            try:
                chart_dict = chart.read(
                    time=time,
                    x_axys=x_axys,
                    timezone=timezone,
                    additional_query_kwargs=self._get_chart_additional_query_kwargs(
                        chart
                    ),
                )
                if not chart_dict['traces']:
                    continue
                chart_dict['description'] = chart.description
                chart_dict['title'] = chart.title.format(
                    metric=chart.metric, **chart.metric.tags
                )
                chart_dict['type'] = chart.type
                chart_dict['unit'] = chart.unit
                chart_dict['summary_labels'] = chart.summary_labels
                chart_dict['colors'] = chart.colors
                chart_dict['colorscale'] = chart.colorscale
                for attr in ['fill', 'xaxis', 'yaxis']:
                    value = getattr(chart, attr)
                    if value:
                        chart_dict[attr] = value
            except InvalidChartConfigException:
                logger.exception(f'Skipped chart for metric {chart.metric}')
                continue
            # get x axys (only once)
            if x_axys and chart_dict['x'] and chart.type != 'histogram':
                data['x'] = chart_dict.pop('x')
                x_axys = False
            # prepare to sort the items according to
            # the order in the chart configuration
            key = f'{chart.order} {chart_dict["title"]}'
            chart_map[key] = chart_dict
        # add sorted chart list to chart data
        data['charts'] = list(OrderedDict(sorted(chart_map.items())).values())
        return data


dashboard_timeseries = DashboardTimeseriesView.as_view()
