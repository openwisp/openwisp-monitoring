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

logger = logging.getLogger(__name__)
Chart = load_model('monitoring', 'Chart')
Metric = load_model('monitoring', 'Metric')
Organization = load_model('openwisp_users', 'Organization')


class DashboardTimeseriesView(APIView):
    def _get_organization_lookup(self):
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
                orgs = org_ids
            else:
                raise PermissionDenied
        else:
            if self.request.user.is_superuser:
                orgs = []
            elif self.request.user.organizations_managed:
                orgs = self.request.user.organizations_managed
            else:
                raise PermissionDenied

        if not orgs:
            return ''
        org_lookup = []
        for org in orgs:
            org_lookup.append(f"organization_id = '{org}'")
        return 'AND ({org_lookup})'.format(org_lookup=' OR '.join(org_lookup))

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
                    additional_query_kwargs={
                        'additional_params': {'organization_lookup': org_lookup}
                    },
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
