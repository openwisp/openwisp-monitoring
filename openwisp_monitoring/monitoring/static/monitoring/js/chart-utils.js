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

    function setDateRangePickerWidget(pickerStartDate, pickerEndDate) {
      addDateRangePickerLabel(pickerStartDate.format('MMMM D, YYYY'), pickerEndDate.format('MMMM D, YYYY'));
      $('#daterangepicker-widget').data('daterangepicker').setStartDate(moment(pickerStartDate.format('MMMM D, YYYY')).format('MM/DD/YYYY'));
      $('#daterangepicker-widget').data('daterangepicker').setEndDate(moment(pickerEndDate.format('MMMM D, YYYY')).format('MM/DD/YYYY'));
    }
    function isMonitoringChartsLocation() {
      // If active monitoring charts location is not #ow-chart-container and not admin
      return window.location.hash === '#ow-chart-container' ||  window.location.pathname === '/admin/';
    }

    function handleChartZoomChange(chartsContainers) {
      // Simply return if we are not at the monitoring chart location
      if (!isMonitoringChartsLocation()) {
        return;
      }
      // Handle chart zooming with custom dates
      var zoomCharts = document.getElementsByClassName(chartsContainers);
      // Set zoomChartId, required for scrolling after the zoom-in event
      $('.js-plotly-plot').on("click dblclick mouseover mouseout", function () {
        var zoomChartId = $(this).parent().prop('id');
        if (zoomChartId === 'chart-0') {
         var activeChartsLocation = window.location.hash;
         zoomChartId = activeChartsLocation === '#ow-chart-container' ? 'container' : 'ow-chart-inner-container';
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
            // Simply return if we are not at the monitoring chart location
            if (!isMonitoringChartsLocation()) {
              return;
            }
            // When the chart is zoomed out, then load charts with initial zoom level
            if (!eventEnd && !eventStart) {
              localStorage.setItem(isChartZoomed, false);
              localStorage.setItem(isCustomDateRange, false);
              // After zoomed out, it should scroll back initial zoom container
              localStorage.setItem(isChartZoomScroll, true);
              var daysBeforeZoom = localStorage.getItem(timeRangeKey);
              // Set custom date range labels & select custom date ranges for the widget
              var initialStartLabel = localStorage.getItem(startDayKey) || moment().format('MMMM D, YYYY');
              var initialEndLabel = localStorage.getItem(endDayKey) || moment().format('MMMM D, YYYY');
              var initialStartDate = moment(initialStartLabel, 'MMMM D, YYYY');
              var initialEndDate = moment(initialEndLabel, 'MMMM D, YYYY');
              // Set date range picker widget labels
              setDateRangePickerWidget(initialStartDate, initialEndDate);
              // On zoom out, load all charts to their initial zoom level
              loadCharts(daysBeforeZoom, true);
              // refresh every 2.5 minutes
              clearInterval(window.owChartRefresh);
              window.owChartRefresh = setInterval(loadFetchedCharts,
                1000 * 60 * 2.5,
                daysBeforeZoom
              );
              return;
            }
            // When the chart zoomed in,
            var pickerEndDate = moment(eventEnd);
            var pickerStartDate = moment(eventStart);
            var pickerDays = pickerEndDate.diff(pickerStartDate, 'days') + 'd';
            if (pickerDays === '0d') {
              pickerDays = '1d';
            }
            // Set custom date range values
            localStorage.setItem(zoomStartDateTimeKey, pickerStartDate.format('YYYY-MM-DD HH:mm:ss'));
            localStorage.setItem(zoomEndDateTimeKey, pickerEndDate.format('YYYY-MM-DD HH:mm:ss'));
            localStorage.setItem(zoomStartDayKey, pickerStartDate.format('MMMM D, YYYY'));
            localStorage.setItem(zoomEndDayKey, pickerEndDate.format('MMMM D, YYYY'));
            localStorage.setItem(isChartZoomScroll, true);
            localStorage.setItem(isChartZoomed, true);
            localStorage.setItem(isCustomDateRange, true);
            localStorage.setItem(zoomtimeRangeKey, pickerDays);
            // Set date range picker widget labels
            setDateRangePickerWidget(pickerStartDate, pickerEndDate);
            // Now, load the charts with custom date ranges
            loadCharts(pickerDays, true);
            // refresh every 2.5 minutes
            clearInterval(window.owChartRefresh);
            window.owChartRefresh = setInterval(loadFetchedCharts,
              1000 * 60 * 2.5,
              pickerDays
            );
          }
        );
      }
    }

    function triggerZoomCharts (containerClassName) {
      handleChartZoomChange(containerClassName);
      const zoomChartContainer = document.getElementById(localStorage.getItem(zoomChartIdKey));
      // If the chart zoom scrolling is active, then scroll to the zoomed chart container
      if (localStorage.getItem(isChartZoomScroll) === 'true' && zoomChartContainer) {
        zoomChartContainer.scrollIntoView();
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
      getChartFetchUrl = function (time) {
        var url = baseUrl + time;
        // pass pickerEndDate and pickerStartDate to url
        if (localStorage.getItem(isCustomDateRange) === 'true' || localStorage.getItem(pickerChosenLabelKey) === 'Custom Range') {
          var startDate = localStorage.getItem(startDateTimeKey);
          var endDate = localStorage.getItem(endDateTimeKey);
          if (localStorage.getItem(isChartZoomed) === 'true') {
            endDate = localStorage.getItem(zoomEndDateTimeKey);
            startDate = localStorage.getItem(zoomStartDateTimeKey);
          }
          // Ensure that the 'endDate' of zooming events
          // is never greater than the 'now' date time
          const now = moment().format('YYYY-MM-DD HH:mm:ss');
          const endDateTime = moment(endDate).format('YYYY-MM-DD HH:mm:ss');
          endDate = endDateTime > now ? now : endDateTime;
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
            triggerZoomCharts('js-plotly-plot');
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
      
      // Disable the zoom chart and scrolling when we refresh the page
      localStorage.setItem(isChartZoomScroll, false);
      localStorage.setItem(isChartZoomed, false);

      if (localStorage.getItem(isCustomDateRange) === 'true') {
        // Add label to daterangepicker widget
        addDateRangePickerLabel(startLabel, endLabel);
        // Set last selected custom date after page reload
        var startDate = moment(startLabel, 'MMMM D, YYYY');
        var endDate = moment(endLabel, 'MMMM D, YYYY');
        $('#daterangepicker-widget').data('daterangepicker').setStartDate(moment(startDate).format('MM/DD/YYYY'));
        $('#daterangepicker-widget').data('daterangepicker').setEndDate(moment(endDate).format('MM/DD/YYYY'));
        // Then loads charts with custom ranges selected
        loadCharts(range, true);
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
      localStorage.setItem(pickerChosenLabelKey, pickerChosenLabel);
      localStorage.setItem(startDateTimeKey, picker.startDate.format('YYYY-MM-DD HH:mm:ss'));
      localStorage.setItem(endDateTimeKey, picker.endDate.format('YYYY-MM-DD HH:mm:ss'));
      localStorage.setItem(startDayKey, pickerStart.format('MMMM D, YYYY'));
      localStorage.setItem(endDayKey, pickerEnd.format('MMMM D, YYYY'));
      localStorage.setItem(isChartZoomed, false);
      localStorage.setItem(isChartZoomScroll, false);
      localStorage.setItem(timeRangeKey, pickerDays);
      localStorage.setItem(isCustomDateRange, pickerChosenLabel === "Custom Range");
      loadCharts(pickerDays, true);
      // refresh charts every 2.5 minutes
      clearInterval(window.owChartRefresh);
      window.owChartRefresh = setInterval(loadFetchedCharts,
        1000 * 60 * 2.5,
        pickerDays
      );
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
    // fetch chart data and replace the old charts with the new ones
    function loadFetchedCharts(time){
      $.ajax(getChartFetchUrl(time), {
        dataType: 'json',
        success: function (data) {
          if (data.charts.length) {
            createCharts(data);
            triggerZoomCharts('js-plotly-plot');
          }
        },
        error: function () {
          window.console.error('Unable to fetch chart data.');
        },
      });
    }
  });
}(django.jQuery));
