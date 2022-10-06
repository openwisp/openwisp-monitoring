'use strict';
const isCustomDateRange = 'ow2-chart-custom-daterange'; // true/false
const timeRangeKey = 'ow2-chart-time-range'; // 30d
const startDayKey = 'ow2-chart-start-day'; // September 3, 2022
const endDayKey = 'ow2-chart-end-day'; // October 3, 2022
const startDateTimeKey = 'ow2-chart-start-datetime'; // 2022-09-03 00:00:00
const endDateTimeKey = 'ow2-chart-end-datetime'; // 2022-09-03 00:00:00

django.jQuery(function ($) {
  $(document).ready(function () {
    var pickerStart, pickerEnd, pickerDays, pickerChosenLabel, start = moment(), end = moment();
      function initDateRangePickerWidget(start, end) {
        $('#daterangepicker-widget span').html(start.format('MMMM D, YYYY') + ' - ' + end.format('MMMM D, YYYY'));
        $("[data-range-key='1 day']").attr('data-time', '1d');
        $("[data-range-key='3 days']").attr('data-time', '3d');
        $("[data-range-key='1 week']").attr('data-time', '7d');
        $("[data-range-key='1 month']").attr('data-time', '30d');
        $("[data-range-key='1 year']").attr('data-time', '365d');
        $("[data-range-key='Custom Range']").attr('data-time', 'Custom Range');
      }

      $('#daterangepicker-widget').daterangepicker({
        startDate: start,
        endDate: end,
        maxDate: moment(),
        maxSpan: {
          "year": 1,
        },
        ranges: {
          '1 day': [moment().subtract(1, 'days'), moment()],
          '3 days': [moment().subtract(3, 'days'), moment()],
          '1 week': [moment().subtract(7, 'days'), moment()],
          '1 month': [moment().subtract(30, 'days'), moment()],
          '1 year': [moment().subtract(365, 'days'), moment()],
        }
      }, initDateRangePickerWidget);
      initDateRangePickerWidget(start, end);

    var chartQuickLinks, chartContents = $('#ow-chart-contents'),
      fallback = $('#ow-chart-fallback'),
      defaultTimeRange = localStorage.getItem(timeRangeKey) || $('#monitoring-timeseries-default-time').data('value'),
      apiUrl = $('#monitoring-timeseries-api-url').data('value'),
      originalKey = $('#monitoring-timeseries-original-key').data('value'),
      baseUrl = `${apiUrl}?key=${originalKey}&time=`,
      globalLoadingOverlay = $('#loading-overlay'),
      localLoadingOverlay = $('#chart-loading-overlay'),

      loadCharts = function (time, showLoading) {
        var url = baseUrl + time;
        $.ajax(url, {
          dataType: 'json',
          beforeSend: function () {
            chartContents.hide();
            chartContents.empty();
            fallback.hide();
            if (showLoading) {
              globalLoadingOverlay.show();
            }
            localLoadingOverlay.show();
          },
          success: function (data) {
            localLoadingOverlay.hide();
            if (data.charts.length) {
              chartContents.show();
            } else {
              fallback.show();
            }
            $.each(data.charts, function (i, chart) {
              var htmlId = 'chart-' + i,
                chartDiv = $('#' + htmlId),
                chartQuickLink = chartQuickLinks[chart.title];
              if (!chartDiv.length) {
                chartContents.append(
                  '<div id="' + htmlId + '" class="ow-chart">' +
                  '<div class="js-plotly-plot"></div></div>'
                );
              }
              createChart(chart, data.x, htmlId, chart.title, chart.type, chartQuickLink);
            });
          },
          error: function () {
            alert('Something went wrong while loading the charts');
          },
          complete: function () {
            localLoadingOverlay.fadeOut(200, function() {
              if (showLoading) {
                globalLoadingOverlay.fadeOut(200);
              }
            });
          }
        });
      };
    try {
      chartQuickLinks = JSON.parse($('#monitoring-chart-quick-links').html());
    } catch (error) {
      chartQuickLinks = {};
    }

    window.triggerChartLoading = function() {
      // Charts load with the last set time range or default time range
      var range = localStorage.getItem(timeRangeKey) || defaultTimeRange;
      var startLabel = localStorage.getItem(startDayKey) || moment().format('MMMM D, YYYY');
      var endLabel = localStorage.getItem(endDayKey) || moment().format('MMMM D, YYYY');
      // Add label to daterangepicker widget
      $('#daterangepicker-widget span').html(startLabel + ' - ' + endLabel);
      $('.daterangepicker .ranges ul li[data-time=' + range + ']').trigger('click');
    };
    // try adding the browser timezone to the querystring
    try {
      var timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
      baseUrl = baseUrl.replace('time=', 'timezone=' + timezone + '&time=');
      // ignore failures (older browsers do not support this)
    } catch (e) {}

    // daterangepicker widget logic here
    $("#daterangepicker-widget").on('apply.daterangepicker', function (ev, picker) {
    pickerChosenLabel = picker.chosenLabel;
    pickerStart = moment(picker.startDate.format('YYYY-MM-DD HH:mm:ss'));
    pickerEnd = moment(picker.endDate.format('YYYY-MM-DD HH:mm:ss'));
    pickerDays = pickerEnd.diff(pickerStart, 'days') + 'd';

    // set date values required for daterangepicker labels
    localStorage.setItem(startDateTimeKey, picker.startDate.format('YYYY-MM-DD HH:mm:ss'));
    localStorage.setItem(endDateTimeKey, picker.endDate.format('YYYY-MM-DD HH:mm:ss'));
    localStorage.setItem(startDayKey, pickerStart.format('MMMM D, YYYY'));
    localStorage.setItem(endDayKey, pickerEnd.format('MMMM D, YYYY'));

    // daterangepicker with custom time ranges
    if (pickerChosenLabel === "Custom Range") {
      loadCharts(pickerDays, true);
      localStorage.setItem(isCustomDateRange, true);
      localStorage.setItem(timeRangeKey, pickerDays);
      // refresh every 2.5 minutes
      clearInterval(window.owChartRefresh);
      window.owChartRefresh = setInterval(loadCharts,
        1000 * 60 * 2.5,
        pickerDays,
        false
      );}

    // daterangepicker with default time ranges
    else {
      loadCharts(pickerDays, true);
      localStorage.setItem(isCustomDateRange, false);
      localStorage.setItem(timeRangeKey, pickerDays);
      // refresh every 2.5 minutes
      clearInterval(window.owChartRefresh);
      window.owChartRefresh = setInterval(loadCharts,
        1000 * 60 * 2.5,
        pickerDays,
        false
      );}

    });
    // bind export button
    $('#ow-chart-time a.export').click(function () {
      var time = localStorage.getItem(timeRangeKey);
      location.href = baseUrl + time + '&csv=1';
    });
  });
}(django.jQuery));
