'use strict';
const isCustomDateRange = 'ow2-chart-custom-daterange'; // true/false
const timeRangeKey = 'ow2-chart-time-range'; // 30d
const startDayKey = 'ow2-chart-start-day'; // September 3, 2022
const endDayKey = 'ow2-chart-end-day'; // October 3, 2022
const startDateTimeKey = 'ow2-chart-start-datetime'; // 2022-09-03 00:00:00
const endDateTimeKey = 'ow2-chart-end-datetime'; // 2022-09-03 00:00:00

django.jQuery(function ($) {
  $(document).ready(function () {
    var pickerStart, pickerEnd, pickerDays, pickerChosenLabel, end = moment();
    var range = localStorage.getItem(timeRangeKey) || $('#monitoring-timeseries-default-time').data('value');
    var start = localStorage.getItem(isCustomDateRange) === 'true' ? moment() : moment().subtract(range.split('d')[0], 'days');

      // Add label to daterangepicker widget
      function addDateRangePickerLabel(startDate, endDate) {
        $('#daterangepicker-widget span').html(startDate + ' - ' + endDate);
      }

      function initDateRangePickerWidget(start, end) {
        addDateRangePickerLabel(start.format('MMMM D, YYYY'), end.format('MMMM D, YYYY'));
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

    var chartQuickLinks, chartContents = $('#ow-chart-contents'),
      fallback = $('#ow-chart-fallback'),
      defaultTimeRange = localStorage.getItem(timeRangeKey) || $('#monitoring-timeseries-default-time').data('value'),
      apiUrl = $('#monitoring-timeseries-api-url').data('value'),
      originalKey = $('#monitoring-timeseries-original-key').data('value'),
      baseUrl = `${apiUrl}?key=${originalKey}&time=`,
      globalLoadingOverlay = $('#loading-overlay'),
      localLoadingOverlay = $('#chart-loading-overlay'),
      getChartFetchUrl = function (time) {
        var url = baseUrl + time;
        // pass pickerEndDate and pickerStartDate to url
        if (localStorage.getItem(isCustomDateRange) === 'true') {
          var startDate = localStorage.getItem(startDateTimeKey);
          var endDate = localStorage.getItem(endDateTimeKey);
          var timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
          url = `${apiUrl}?key=${originalKey}&timezone=${timezone}&start=${startDate}&end=${endDate}`;
        }
        return url;
      },
      createCharts = function (data){
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
      loadCharts = function (time, showLoading) {
        $.ajax(getChartFetchUrl(time), {
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
            createCharts(data);
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
      var startLabel, endLabel, range = localStorage.getItem(timeRangeKey) || defaultTimeRange;
      if (localStorage.getItem(isCustomDateRange) === 'true') {
        startLabel = localStorage.getItem(startDayKey) || moment();
        endLabel = localStorage.getItem(endDayKey) || moment();
        // Add label to daterangepicker widget
        addDateRangePickerLabel(startLabel, endLabel);
        // Set last selected custom date after page reload
        var startDate = moment(startLabel, 'MMMM D, YYYY');
        var endDate = moment(endLabel, 'MMMM D, YYYY');
        $('#daterangepicker-widget').data('daterangepicker').setStartDate(moment(startDate).format('MM/DD/YYYY'));
        $('#daterangepicker-widget').data('daterangepicker').setEndDate(moment(endDate).format('MM/DD/YYYY'));
        // Then loads charts with custom ranges selected
        loadCharts(localStorage.getItem(timeRangeKey), true);
      }
      else {
        endLabel =  moment().format('MMMM D, YYYY');
        startLabel = moment().subtract(range.split('d')[0], 'days').format('MMMM D, YYYY');
        // Add label to daterangepicker widget
        addDateRangePickerLabel(startLabel, endLabel);
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
      localStorage.setItem(isCustomDateRange, pickerChosenLabel === "Custom Range");
      localStorage.setItem(timeRangeKey, pickerDays);
      loadCharts(pickerDays, true);
      // refresh charts every 2.5 minutes
      clearInterval(window.owChartRefresh);
      window.owChartRefresh = setInterval(loadFetchedCharts,
        1000 * 60 * 2.5,
        pickerDays,
        false
      );
    });
    // bind export button
    $('#ow-chart-time a.export').click(function () {
      var time = localStorage.getItem(timeRangeKey);
      location.href = baseUrl + time + '&csv=1';
      // If custom pass pickerEndDate and pickerStartDate to csv url
      if (localStorage.getItem(isCustomDateRange) === 'true') {
      var startDate = localStorage.getItem(startDateTimeKey);
      var endDate = localStorage.getItem(endDateTimeKey);
      var timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
      location.href = `${apiUrl}?key=${originalKey}&timezone=${timezone}&start=${startDate}&end=${endDate}&csv=1`;
      }
    });
    // fetch chart data and replace the old charts with the new ones
    function loadFetchedCharts(time){
      $.ajax(getChartFetchUrl(time), {
        dataType: 'json',
        success: function (data) {
          createCharts(data);
        },
        error: function () {
          window.console.error('Unable to fetch chart data.');
        },
      });
    }
  });
}(django.jQuery));
