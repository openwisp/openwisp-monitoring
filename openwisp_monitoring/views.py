import csv
import datetime as dt
import logging
from collections import OrderedDict
from io import StringIO

import pytz
from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse
from pytz import timezone as tz
from pytz.exceptions import UnknownTimeZoneError
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from swapper import load_model

from .monitoring.exceptions import InvalidChartConfigException

utc = pytz.UTC

logger = logging.getLogger(__name__)
device = load_model('config', 'Device')
Chart = load_model('monitoring', 'Chart')


class MonitoringApiViewMixin:
    def _get_charts(self, request, *args, **kwargs):
        """
        Hook to return Chart query.
        """
        raise NotImplementedError

    def _get_additional_data(request, *args, **kwargs):
        """
        Hook to return any additonal data that should be
        included in the response.
        """
        return {}

    def get_date_range(self, request, *args, **kwargs):
        start_date = request.GET.get('start')
        end_date = request.GET.get('end')
        return start_date, end_date

    def get_group_map(self, daterange):
        value = '10m'
        if daterange:
            daterange = int(daterange)
            if daterange >= 0 and daterange < 3:
                value = '10m'
            elif daterange >= 3 and daterange < 7:
                value = str(round((daterange / 3) * 20)) + 'm'
            elif daterange >= 7 and daterange < 28:
                value = str(round((daterange / 7) * 1)) + 'h'
            elif daterange >= 28 and daterange < 365:
                value = str(round((daterange / 28) * 24)) + 'h'
            elif daterange == 365:
                value = '24h'

        daterange = str(daterange) + 'd'
        Chart.GROUP_MAP.update({daterange: value})

    def get(self, request, *args, **kwargs):
        daterange = request.GET.get('dateSpan')
        if daterange:
            self.get_group_map(daterange)
        start_date, end_date = self.get_date_range(request, *args, **kwargs)
        if start_date is not None and end_date is not None:
            start_date = dt.datetime.strptime(
                start_date, '%Y-%m-%d %H:%M:%S.%f%z'
            ).replace(tzinfo=utc)
            end_date = dt.datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S.%f%z').replace(
                tzinfo=utc
            )
            if end_date < start_date:
                messages.error(request, 'End date should be greater than start date')
        time = request.query_params.get('time', Chart.DEFAULT_TIME)
        if time not in Chart.GROUP_MAP.keys():
            raise ValidationError('Time range not supported')
        # try to read timezone
        timezone = request.query_params.get('timezone', settings.TIME_ZONE)
        try:
            tz(timezone)
        except UnknownTimeZoneError:
            raise ValidationError('Unkown Time Zone')
        charts = self._get_charts(request, *args, **kwargs)
        # prepare response data
        data = self._get_charts_data(charts, time, timezone)
        # csv export has a different response
        if request.query_params.get('csv'):
            response = HttpResponse(self._get_csv(data), content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename=data.csv'
            return response
        data.update(self._get_additional_data(request, *args, **kwargs))
        return Response(data)

    def _get_chart_additional_query_kwargs(self, chart):
        """
        Hook to provide additional kwargs to Chart.read.
        """
        return None

    def _get_charts_data(self, charts, time, timezone):
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
                if chart.trace_type:
                    chart_dict['trace_type'] = chart.trace_type
                if chart.trace_order:
                    chart_dict['trace_order'] = chart.trace_order
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
