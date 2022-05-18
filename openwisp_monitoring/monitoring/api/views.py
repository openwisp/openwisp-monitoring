import logging
from datetime import datetime

from django.conf import settings
from django.http import HttpResponse
from pytz import timezone as tz
from pytz.exceptions import UnknownTimeZoneError
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView
from swapper import load_model

from ...db import default_chart_query, timeseries_db
from ..configuration import DEFAULT_METRICS

logger = logging.getLogger(__name__)
Chart = load_model('monitoring', 'Chart')
Metric = load_model('monitoring', 'Metric')
Organization = load_model('openwisp_users', 'Organization')


class DashboardTimeseriesView(APIView):
    def _get_organization_lookup(self):
        query_org = self.request.query_params.get('organization_slug')
        if query_org:
            org = get_object_or_404(Organization, slug=query_org)
            if (
                self.request.user.is_superuser
                or org.id in self.request.user.organizations_managed
            ):
                return [org.id]
        else:
            if self.request.user.is_superuser:
                return None
            else:
                return self.request.user.organizations_managed

    def get(self, request):
        metric = request.get('metric')
        if metric not in DEFAULT_METRICS.keys():
            return Response(
                {'detail': '"metric" query parameter is required'}, status=400
            )
        # determine time range
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
        data = self.read(metric, time=time, timezone=timezone)
        # csv export has a different response
        if request.query_params.get('csv'):
            response = HttpResponse(self._get_csv(data), content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename=data.csv'
            return response
        # add device data if requested
        if request.query_params.get('status', False):
            data['data'] = self.instance.data
        return Response(data)

    def read(
        self,
        metric,
        decimal_places=2,
        time=Chart.DEFAULT_TIME,
        x_axys=True,
        timezone=settings.TIME_ZONE,
    ):
        traces = {}
        if x_axys:
            x = []
        try:
            top_fields = DEFAULT_METRICS[metric].get('top_fields')
            query_kwargs = dict(time=time, timezone=timezone)
            if top_fields:
                fields = self.get_top_fields(top_fields)
                data_query = self.get_query(fields=fields, **query_kwargs)
                summary_query = self.get_query(
                    fields=fields, summary=True, **query_kwargs
                )
            else:
                data_query = self.get_query(**query_kwargs)
                summary_query = self.get_query(summary=True, **query_kwargs)
            points = timeseries_db.get_list_query(data_query)
            summary = timeseries_db.get_list_query(summary_query)
        except timeseries_db.client_error as e:
            logging.error(e, exc_info=True)
            raise e
        for point in points:
            for key, value in point.items():
                if key == 'time':
                    continue
                traces.setdefault(key, [])
                traces[key].append(value)
            time = datetime.fromtimestamp(point['time'], tz=tz(timezone)).strftime(
                '%Y-%m-%d %H:%M'
            )
            if x_axys:
                x.append(time)
        # prepare result to be returned
        # (transform chart data so its order is not random)
        result = {'traces': sorted(traces.items())}
        if x_axys:
            result['x'] = x
        # add summary
        if len(summary) > 0:
            result['summary'] = {}
            for key, value in summary[0].items():
                if key == 'time':
                    continue
                if not timeseries_db.validate_query(self.query):
                    value = None
                result['summary'][key] = value
        return result

    def get_top_fields(self, number):
        """
        Returns list of top ``number`` of fields (highest sum) of a
        measurement in the specified time range (descending order).
        """
        query = default_chart_query[0].replace('{field_name}', '{fields}')
        params = self._get_query_params(self.DEFAULT_TIME)
        return timeseries_db._get_top_fields(
            query=query,
            chart_type=self.type,
            group_map=self.GROUP_MAP,
            number=number,
            params=params,
            time=self.DEFAULT_TIME,
        )

    def get_query(
        self,
        metric,
        time=Chart.DEFAULT_TIME,
        summary=False,
        fields=None,
        query=None,
        timezone=settings.TIME_ZONE,
    ):
        query = DEFAULT_METRICS[metric].get('query')
        params = self._get_query_params(time)
        return timeseries_db.get_query(
            self.type, params, time, self.GROUP_MAP, summary, fields, query, timezone
        )

    def _get_query_params(self, metric, time):
        params = dict(
            field_name=DEFAULT_METRICS[metric].get('field_name'),
            key=DEFAULT_METRICS[metric].get('key'),
            time=self._get_time(time),
            organization=self._get_organization_lookup(),
        )
        return params


dashboard_timeseries = DashboardTimeseriesView.as_view()
