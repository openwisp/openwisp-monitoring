'use strict';
const isChartZoomed = 'ow2-chart-custom-zoom'; // true/false
const isChartZoomScroll = 'ow2-chart-custom-zoom-scroll'; // true/false
const isCustomDateRange = 'ow2-chart-custom-daterange'; // true/false
const timeRangeKey = 'ow2-chart-time-range'; // 30d
const startDayKey = 'ow2-chart-start-day'; // September 3, 2022
const endDayKey = 'ow2-chart-end-day'; // October 3, 2022
const startDateTimeKey = 'ow2-chart-start-datetime'; // 2022-09-03 00:00:00
const endDateTimeKey = 'ow2-chart-end-datetime'; // 2022-09-03 00:00:00
const pickerChosenLabelKey = 'ow2-chart-picker-label'; // 2022-09-03 00:00:00
const zoomtimeRangeKey = 'ow2-chart-zoom-time-range'; // 30d
const zoomStartDayKey = 'ow2-chart-zoom-start-day'; // September 3, 2022
const zoomEndDayKey = 'ow2-chart-zoom-end-day'; // October 3, 2022
const zoomStartDateTimeKey = 'ow2-chart-zoom-start-datetime'; // 2022-09-03 00:00:00
const zoomEndDateTimeKey = 'ow2-chart-zoom-end-datetime'; // 2022-09-03 00:00:00
const zoomChartIdKey = 'ow2-chart-zoom-id'; // true/false

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

    function handleChartZoomChange(chartsContainers) {
      // Handle chart zooming with custom dates
      var zoomCharts = document.getElementsByClassName(chartsContainers);
      // Set zoomChartId, required for scrolling after the zoom event
      $('.js-plotly-plot').on("click dblclick mouseover mouseout", function () {
        var zoomChartId = $(this).parent().prop('id');
        if (zoomChartId === 'chart-0') {
          zoomChartId = 'container';
        }
        localStorage.setItem(zoomChartIdKey, zoomChartId);
      });
      for (var zoomChart of zoomCharts) {
        if (!zoomChart) {
          localStorage.setItem(isChartZoomed, false);
          localStorage.setItem(isCustomDateRange, false);
          return;
        }
        zoomChart.on('plotly_relayout',
          function (eventdata) { // jshint ignore:line
            var eventEnd = eventdata['xaxis.range[1]'];
            var eventStart = eventdata['xaxis.range[0]'];
            // When the chart is zoomed out, then load charts with initial zoom level
            if (!eventEnd || !eventStart) {
              localStorage.setItem(isChartZoomed, false);
              localStorage.setItem(isCustomDateRange, false);
              // After zoomed out, it should scroll back initial zoom container
              localStorage.setItem(isChartZoomScroll, true);
              var daysBeforeZoom = localStorage.getItem(timeRangeKey);
              // Set custom date range labels & select custom date ranges for the widget
              var initialStartLabel = localStorage.getItem(startDayKey) || moment().format('MMMM D, YYYY');
              var initialEndLabel = localStorage.getItem(endDayKey) || moment().format('MMMM D, YYYY');
              var initialstartDate = moment(initialStartLabel, 'MMMM D, YYYY');
              var initialEndDate = moment(initialEndLabel, 'MMMM D, YYYY');
              $('#daterangepicker-widget span').html(initialstartDate.format('MMMM D, YYYY') + ' - ' + initialEndDate.format('MMMM D, YYYY'));
              $('#daterangepicker-widget').data('daterangepicker').setStartDate(moment(initialstartDate.format('MMMM D, YYYY')).format('MM/DD/YYYY'));
              $('#daterangepicker-widget').data('daterangepicker').setEndDate(moment(initialEndDate.format('MMMM D, YYYY')).format('MM/DD/YYYY'));
              loadCharts(daysBeforeZoom, true);
              // refresh every 2.5 minutes
              clearInterval(window.owChartRefresh);
              window.owChartRefresh = setInterval(loadCharts,
                1000 * 60 * 2.5,
                daysBeforeZoom,
                false
              );
              return;
            }
            // When the chart zoomed in,
            var pickerEnd = moment(eventEnd);
            var pickerStart = moment(eventStart);
            var pickerDays = pickerEnd.diff(pickerStart, 'days') + 'd';
            if (pickerDays === '0d') {
              pickerDays = '1d';
            }
            // Set custom date range values
            localStorage.setItem(zoomStartDateTimeKey, pickerStart.format('YYYY-MM-DD HH:mm:ss'));
            localStorage.setItem(zoomEndDateTimeKey, pickerEnd.format('YYYY-MM-DD HH:mm:ss'));
            localStorage.setItem(zoomStartDayKey, pickerStart.format('MMMM D, YYYY'));
            localStorage.setItem(zoomEndDayKey, pickerEnd.format('MMMM D, YYYY'));
            localStorage.setItem(isChartZoomScroll, true);
            localStorage.setItem(isChartZoomed, true);
            localStorage.setItem(isCustomDateRange, true);
            localStorage.setItem(zoomtimeRangeKey, pickerDays);
            // Set custom date range labels & select custom date ranges for the widget
            $('#daterangepicker-widget span').html(pickerStart.format('MMMM D, YYYY') + ' - ' + pickerEnd.format('MMMM D, YYYY'));
            $('#daterangepicker-widget').data('daterangepicker').setStartDate(moment(pickerStart.format('MMMM D, YYYY')).format('MM/DD/YYYY'));
            $('#daterangepicker-widget').data('daterangepicker').setEndDate(moment(pickerEnd.format('MMMM D, YYYY')).format('MM/DD/YYYY'));
            // Now, load the charts with custom date ranges
            loadCharts(pickerDays, true);
            // refresh every 2.5 minutes
            clearInterval(window.owChartRefresh);
            window.owChartRefresh = setInterval(loadCharts,
              1000 * 60 * 2.5,
              pickerDays,
              false
            );
          }
        );
      }
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
        if (localStorage.getItem(isCustomDateRange) === 'true' || localStorage.getItem(pickerChosenLabelKey) === 'Custom Range') {
          var startDate = localStorage.getItem(startDateTimeKey);
          var endDate = localStorage.getItem(endDateTimeKey);
          if (localStorage.getItem(isChartZoomed) === 'true') {
            endDate = localStorage.getItem(zoomEndDateTimeKey);
            startDate = localStorage.getItem(zoomStartDateTimeKey);
          }
          var timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
          url = `${apiUrl}?key=${originalKey}&timezone=${timezone}&start=${startDate}&end=${endDate}`;
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
            handleChartZoomChange('js-plotly-plot');
            const zoomChartContainer = document.getElementById(localStorage.getItem(zoomChartIdKey));
            // If the chart zoom scrolling is active, then scroll to the zoomed chart container
            if (localStorage.getItem(isChartZoomScroll) === 'true' && zoomChartContainer) {
              zoomChartContainer.scrollIntoView();
            }
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
      // Disable zoom charts scrolling on page refresh
      localStorage.setItem(isChartZoomScroll, false);
      if (localStorage.getItem(isChartZoomed) === 'true') {
        range = localStorage.getItem(zoomtimeRangeKey);
        endLabel = localStorage.getItem(zoomEndDayKey);
        startLabel = localStorage.getItem(zoomStartDayKey);
      }
      // Add label to daterangepicker widget
      $('#daterangepicker-widget span').html(startLabel + ' - ' + endLabel);
      if (localStorage.getItem(isCustomDateRange) === 'true' || localStorage.getItem(isChartZoomed) === 'false' ) {
        // Set last selected custom date after page reload
        var startDate = moment(startLabel, 'MMMM D, YYYY');
        var endDate = moment(endLabel, 'MMMM D, YYYY');
        $('#daterangepicker-widget').data('daterangepicker').setStartDate(moment(startDate).format('MM/DD/YYYY'));
        $('#daterangepicker-widget').data('daterangepicker').setEndDate(moment(endDate).format('MM/DD/YYYY'));
        // Then loads charts with custom ranges selected
        loadCharts(range, true);
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
      localStorage.setItem(pickerChosenLabelKey, pickerChosenLabel);
      localStorage.setItem(startDateTimeKey, picker.startDate.format('YYYY-MM-DD HH:mm:ss'));
      localStorage.setItem(endDateTimeKey, picker.endDate.format('YYYY-MM-DD HH:mm:ss'));
      localStorage.setItem(startDayKey, pickerStart.format('MMMM D, YYYY'));
      localStorage.setItem(endDayKey, pickerEnd.format('MMMM D, YYYY'));

      // daterangepicker with custom time ranges
      if (pickerChosenLabel === "Custom Range") {
        localStorage.setItem(isChartZoomed, false);
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
        localStorage.setItem(isChartZoomed, false);
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
      // If custom or pickerChosenLabelKey is 'Custom Range', pass pickerEndDate and pickerStartDate to csv url
      if (localStorage.getItem(isCustomDateRange) === 'true' || localStorage.getItem(pickerChosenLabelKey) === 'Custom Range') {
      var startDate = localStorage.getItem(startDateTimeKey);
      var endDate = localStorage.getItem(endDateTimeKey);
      if (localStorage.getItem(isChartZoomed) === 'true') {
        time = localStorage.getItem(zoomtimeRangeKey);
        endDate = localStorage.getItem(zoomEndDateTimeKey);
        startDate = localStorage.getItem(zoomStartDateTimeKey);
      }
      var timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
      location.href = `${apiUrl}?key=${originalKey}&timezone=${timezone}&start=${startDate}&end=${endDate}&csv=1`;
      }
    });
  });
}(django.jQuery));
