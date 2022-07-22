'use strict';
const timeRangeKey = 'ow2-chart-time-range';

django.jQuery(function ($) {
  $(document).ready(function () {
      /* jshint -W117 */
      var custom = '1d';
      var start = moment();
      var end = moment();
      function custom_range(start_custom, end_custom) {
        start = moment(start_custom);
        end = moment(end_custom);
        return end.diff(start, 'days') + 'd';
      }
      function cb(start, end) {
        var start_custom;
        var end_custom;
          $("#reportrange").on('apply.daterangepicker', function (ev, picker) {
            start_custom = picker.startDate.format('YYYY-MM-DD');
            end_custom = picker.endDate.format('YYYY-MM-DD');
            custom = custom_range(start_custom, end_custom);
          });
        $('#reportrange span').html(start.format('MMMM D, YYYY') + ' - ' + end.format('MMMM D, YYYY'));
        $("[data-range-key='Today']").attr('data-time', '1d');
        $("[data-range-key='3 days']").attr('data-time', '3d');
        $("[data-range-key='1 week']").attr('data-time', '7d');
        $("[data-range-key='1 month']").attr('data-time', '30d');
        $("[data-range-key='1 year']").attr('data-time', '365d');
        $("[data-range-key='Custom Range']").attr('data-time', custom);
        $.ajax({
          url: $("#monitoring-timeseries-api-url").data('value'),
          data: {
            start: start.format('YYYY-MM-DD HH:mm:ss.SSSSSSZZ'),
            end: end.format('YYYY-MM-DD HH:mm:ss.SSSSSSZZ'),
            format: 'json',
            time: custom,
            dateSpan: end.diff(start, 'days'),
            key: $("#monitoring-timeseries-original-key").data('value'),
          }
        });
      }

      $('#reportrange').daterangepicker({
        startDate: start,
        endDate: end,
        maxDate: moment(),
        maxSpan: {
          "year": 1,
        },
        ranges: {
          'Today': [moment(), moment()],
          '3 days': [moment().subtract(3, 'days'), moment()],
          '1 week': [moment().subtract(7, 'days'), moment()],
          '1 month': [moment().subtract(30, 'days'), moment()],
          '1 year': [moment().subtract(365, 'days'), moment()],
        }
      }, cb);
    cb(start, end);

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
            localLoadingOverlay.fadeOut(200, function () {
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
    window.triggerChartLoading = function () {
      var range = localStorage.getItem(timeRangeKey) || defaultTimeRange;
      $('#ow-chart-time a[data-time=' + range + ']').trigger('click');
    };
    loadCharts('1d', true);
    // try adding the browser timezone to the querystring
    try {
      var timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
      baseUrl = baseUrl.replace('time=', 'timezone=' + timezone + '&time=');
      // ignore failures (older browsers do not support this)
    } catch (e) {}
    var dateTimePicker = $('.ranges li');
      dateTimePicker.click(function () {
        var timeRange = $(this).attr('data-time');
        loadCharts(timeRange, true);
        localStorage.setItem(timeRangeKey, timeRange);
        if ("Custom Range" == $(this).attr('data-range-key')) {
          var start_custom, end_custom, dateSpan;
          $("#reportrange").on('apply.daterangepicker', function (ev, picker) {
            start_custom = moment(picker.startDate.format('YYYY-MM-DD'));
            end_custom = moment(picker.endDate.format('YYYY-MM-DD'));
            dateSpan = end_custom.diff(start_custom, 'days') + 'd';
            loadCharts(dateSpan, true);
            localStorage.setItem(timeRangeKey, dateSpan);
          });
        }
        // refresh every 2.5 minutes
        clearInterval(window.owChartRefresh);
        window.owChartRefresh = setInterval(loadCharts,
          1000 * 60 * 2.5,
          timeRange,
          false);
      });
      $('.drp-buttons .applyBtn').on('click', () => {
          var customPicker = $('[data-range-key="Custom Range"]');
          var timeRange = customPicker.attr('data-time');
          loadCharts(timeRange, true);
          localStorage.setItem(timeRangeKey, timeRange);
          // refresh every 2.5 minutes
          clearInterval(window.owChartRefresh);
          window.owChartRefresh = setInterval(loadCharts,
            1000 * 60 * 2.5,
            timeRange,
            false);
      });
    // bind export button
    $('#ow-chart-time a.export').click(function () {
      var time = localStorage.getItem(timeRangeKey);
      location.href = baseUrl + time + '&csv=1';
    });
  });
}(django.jQuery));
