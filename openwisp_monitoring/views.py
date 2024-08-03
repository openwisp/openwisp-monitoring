import csv
import logging
from collections import OrderedDict
from datetime import datetime
from io import StringIO

from django.conf import settings
from django.http import HttpResponse
from pytz import timezone
from pytz import timezone as tz
from pytz.exceptions import UnknownTimeZoneError
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from swapper import load_model

from .monitoring.exceptions import InvalidChartConfigException

logger = logging.getLogger(__name__)

Chart = load_model('monitoring', 'Chart')


class MonitoringApiViewMixin:
    def _get_charts(self, request, *args, **kwargs):
        """Hook to return Chart query."""
        raise NotImplementedError

    def _get_additional_data(request, *args, **kwargs):
        """Hook to return any additonal data that should be included in the response."""
        return {}

    def _validate_custom_date(self, start, end, tmz):
        try:
            start = datetime.strptime(start, '%Y-%m-%d %H:%M:%S')
            end = datetime.strptime(end, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            raise ValidationError(
                'Incorrect custom date format, should be YYYY-MM-DD H:M:S'
            )
        if (end - start).days > 365:
            raise ValidationError("The date range shouldn't be greater than 365 days")
        if start > end:
            raise ValidationError('start_date cannot be greater than end_date')
        now_tz = datetime.now(tz=timezone(tmz)).strftime('%Y-%m-%d %H:%M:%S')
        now = datetime.strptime(now_tz, '%Y-%m-%d %H:%M:%S')
        if start > now:
            raise ValidationError("start_date cannot be greater than today's date")
        if end > now:
            raise ValidationError("end_date cannot be greater than today's date")
        return start, end

    def get(self, request, *args, **kwargs):
        time = request.query_params.get('time', Chart.DEFAULT_TIME)
        start_date = request.query_params.get('start', None)
        end_date = request.query_params.get('end', None)
        # try to read timezone
        timezone = request.query_params.get('timezone', settings.TIME_ZONE)
        try:
            tz(timezone)
        except UnknownTimeZoneError:
            raise ValidationError('Unkown Time Zone')
        # if custom dates are provided then validate custom dates
        if start_date and end_date:
            start_datetime, end_datetime = self._validate_custom_date(
                start_date, end_date, timezone
            )
            # if valid custom dates then calculate custom days
            time = '1d'
            custom_days = (end_datetime - start_datetime).days
            if custom_days:
                time = f'{custom_days}d'
        if time not in Chart._get_group_map(time).keys():
            raise ValidationError('Time range not supported')
        charts = self._get_charts(request, *args, **kwargs)
        # prepare response data
        data = self._get_charts_data(charts, time, timezone, start_date, end_date)
        # csv export has a different response
        if request.query_params.get('csv'):
            response = HttpResponse(self._get_csv(data), content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename=data.csv'
            return response
        data.update(self._get_additional_data(request, *args, **kwargs))
        return Response(data)

    def _get_chart_additional_query_kwargs(self, chart):
        """Hook to provide additional kwargs to Chart.read."""
        return None

    def _get_charts_data(self, charts, time, timezone, start_date, end_date):
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
                    start_date=start_date,
                    end_date=end_date,
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
                if chart.trace_type:
                    chart_dict['trace_type'] = chart.trace_type
                if chart.trace_order:
                    chart_dict['trace_order'] = chart.trace_order
                if chart.calculate_total:
                    chart_dict['calculate_total'] = chart.calculate_total
                if chart.connect_points:
                    chart_dict['connect_points'] = chart.connect_points
                if chart.trace_labels:
                    chart_dict['trace_labels'] = chart.trace_labels
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

    def _get_csv(self, data):
        header = ['time']
        columns = [data.get('x')]
        histograms = []
        for chart in data['charts']:
            if chart['type'] == 'histogram':
                histograms.append(chart)
                continue
            for trace in chart['traces']:
                header.append(self._get_csv_header(chart, trace))
                columns.append(trace[1])
        rows = [header]
        for index, element in enumerate(data.get('x', [])):
            row = []
            for column in columns:
                row.append(column[index])
            rows.append(row)
        for chart in histograms:
            rows.append([])
            rows.append([chart['title']])
            # Export value as 0 if it is None
            for key, value in chart['summary'].items():
                if chart['summary'][key] is None:
                    chart['summary'][key] = 0
            # Sort Histogram on the basis of value in the descending order
            sorted_charts = sorted(
                chart['summary'].items(), key=lambda x: x[1], reverse=True
            )
            for field, value in sorted_charts:
                rows.append([field, value])
        # write CSV to in-memory file object
        fileobj = StringIO()
        csv.writer(fileobj).writerows(rows)
        return fileobj.getvalue()

    def _get_csv_header(self, chart, trace):
        header = trace[0]
        return f'{header} - {chart["title"]}'
