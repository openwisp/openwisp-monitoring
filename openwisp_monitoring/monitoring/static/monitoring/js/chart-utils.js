'use strict';
const isCustomDateRange = 'ow2-chart-custom-daterange'; // true/false
const isChartZoomed = 'ow2-chart-custom-zoom'; // true/false
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
        $("[data-range-key='Last 1 Day']").attr('data-time', '1d');
        $("[data-range-key='Last 3 Days']").attr('data-time', '3d');
        $("[data-range-key='Last Week']").attr('data-time', '7d');
        $("[data-range-key='Last Month']").attr('data-time', '30d');
        $("[data-range-key='Last Year']").attr('data-time', '365d');
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
          'Last 1 Day': [moment().subtract(1, 'days'), moment()],
          'Last 3 Days': [moment().subtract(3, 'days'), moment()],
          'Last Week': [moment().subtract(7, 'days'), moment()],
          'Last Month': [moment().subtract(30, 'days'), moment()],
          'Last Year': [moment().subtract(365, 'days'), moment()],
        }
      }, initDateRangePickerWidget);
      initDateRangePickerWidget(start, end);

    function handleChartZoomChange(chartsId) {
      // Handle chart zooming with custom dates
      var zoomChart = document.getElementById(chartsId);
      zoomChart.on('plotly_relayout',
        function (eventdata) {
          var pickerEnd = moment(eventdata['xaxis.range[1]']);
          var pickerStart = moment(eventdata['xaxis.range[0]']);
          var pickerDays = pickerEnd.diff(pickerStart, 'days') + 'd';
          if (pickerDays === '0d') {
            pickerDays = '1d';
          }
          // Set custom date range values
          localStorage.setItem(startDateTimeKey, pickerStart.format('YYYY-MM-DD HH:mm:ss'));
          localStorage.setItem(endDateTimeKey, pickerEnd.format('YYYY-MM-DD HH:mm:ss'));
          localStorage.setItem(startDayKey, pickerStart.format('MMMM D, YYYY'));
          localStorage.setItem(endDayKey, pickerEnd.format('MMMM D, YYYY'));
          localStorage.setItem(isCustomDateRange, true);
          localStorage.setItem(timeRangeKey, pickerDays);
          localStorage.setItem(isChartZoomed, true);
          // Set custom date range labels & select custom date ranges for the widget
          $('#daterangepicker-widget span').html(pickerStart.format('MMMM D, YYYY') + ' - ' + pickerEnd.format('MMMM D, YYYY'));
          $('#daterangepicker-widget').data('daterangepicker').setStartDate(moment(pickerStart.format('MMMM D, YYYY')).format('MM/DD/YYYY'));
          $('#daterangepicker-widget').data('daterangepicker').setEndDate(moment(pickerEnd.format('MMMM D, YYYY')).format('MM/DD/YYYY'));
          // Now, load the charts with custom date ranges
          loadCharts(pickerDays, true);
          // refresh every 2.5 minutes
          // clearInterval(window.owChartRefresh);
          window.owChartRefresh = setInterval(loadCharts,
            1000 * 60 * 2.5,
            pickerDays,
            false
          );
        }
      );
    }

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
        // pass pickerEndDate and pickerStartDate to url
        if (localStorage.getItem(isCustomDateRange) === 'true') {
          var startDate = localStorage.getItem(startDateTimeKey);
          var endDate = localStorage.getItem(endDateTimeKey);
          url = `${baseUrl}${time}&start=${startDate}&end=${endDate}`;
        }
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
                  '<div id="js-plotly-zoom" class="js-plotly-plot"></div></div>'
                );
              }
              createChart(chart, data.x, htmlId, chart.title, chart.type, chartQuickLink);
              handleChartZoomChange('js-plotly-zoom');
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
      if (localStorage.getItem(isCustomDateRange) === 'true') {
        // Set last selected custom date after page reload
        var startDate = moment(startLabel, 'MMMM D, YYYY');
        var endDate = moment(endLabel, 'MMMM D, YYYY');
        $('#daterangepicker-widget').data('daterangepicker').setStartDate(moment(startDate).format('MM/DD/YYYY'));
        $('#daterangepicker-widget').data('daterangepicker').setEndDate(moment(endDate).format('MM/DD/YYYY'));
        // Then loads charts with custom ranges selected
        loadCharts(localStorage.getItem(timeRangeKey), true);
      }
      else {
        // Set last selected default dates after page reload
        $('.daterangepicker .ranges ul li[data-time=' + range + ']').trigger('click');
      }
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
        localStorage.setItem(isCustomDateRange, true);
        localStorage.setItem(timeRangeKey, pickerDays);
        loadCharts(pickerDays, true);
        // refresh every 2.5 minutes
        clearInterval(window.owChartRefresh);
        window.owChartRefresh = setInterval(loadCharts,
          1000 * 60 * 2.5,
          pickerDays,
          false
        );}

      // daterangepicker with default time ranges
      else {
        localStorage.setItem(isCustomDateRange, false);
        localStorage.setItem(timeRangeKey, pickerDays);
        loadCharts(pickerDays, true);
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
      // If custom pass pickerEndDate and pickerStartDate to csv url
      if (localStorage.getItem(isCustomDateRange) === 'true') {
      var startDate = localStorage.getItem(startDateTimeKey);
      var endDate = localStorage.getItem(endDateTimeKey);
      location.href = `${baseUrl}${time}&start=${startDate}&end=${endDate}&csv=1`;
      }
    });
  });
}(django.jQuery));
