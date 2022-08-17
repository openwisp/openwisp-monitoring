'use strict';
const timeRangeKey = 'ow2-chart-time-range';
const startCustomDate = 'ow2-chart-start-time';
const endCustomDate = 'ow2-chart-end-time';
const isCustomKey = 'ow2-chart-is-custom';
const startDateKey = 'ow2-chart-start';
const endDateKey = 'ow2-chart-end';

django.jQuery(function ($) {
  $(document).ready(function () {
      var custom = '1d',
      start = moment(),
      end = moment();
      function cb(start, end) {
        var startCustom, endCustom;
          $("#reportrange").on('apply.daterangepicker', function (ev, picker) {
            startCustom = moment(picker.startDate.format('YYYY-MM-DD HH:mm:ss'));
            endCustom = moment(picker.endDate.format('YYYY-MM-DD HH:mm:ss'));
            custom = endCustom.diff(startCustom, 'days') + 'd';
            localStorage.setItem(startDateKey, picker.startDate.format('YYYY-MM-DD HH:mm:ss'));
            localStorage.setItem(endDateKey, picker.endDate.format('YYYY-MM-DD HH:mm:ss'));
            localStorage.setItem(startCustomDate, startCustom.format('MMMM D, YYYY'));
            localStorage.setItem(endCustomDate, endCustom.format('MMMM D, YYYY'));
          });
        $('#reportrange span').html(start.format('MMMM D, YYYY') + ' - ' + end.format('MMMM D, YYYY'));
        $("[data-range-key='1 day']").attr('data-time', '1d');
        $("[data-range-key='3 days']").attr('data-time', '3d');
        $("[data-range-key='1 week']").attr('data-time', '7d');
        $("[data-range-key='1 month']").attr('data-time', '30d');
        $("[data-range-key='1 year']").attr('data-time', '365d');
        $("[data-range-key='Custom Range']").attr('data-time', custom);
      }

      $('#reportrange').daterangepicker({
        startDate: start,
        endDate: end,
        maxDate: moment(),
        maxSpan: {
          "year": 1,
        },
        ranges: {
          '1 day': [moment().subtract(1,'days'), moment()],
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
      isCustom = false,
      loadCharts = function (time, showLoading, isCustom, startDate, endDate) {
        var daterange = `&start=${startDate}&end=${endDate}`;
        isCustom = localStorage.getItem(isCustomKey) || isCustom;
        var custom =  `&custom=${isCustom}`;
        var url = baseUrl + time + daterange + custom;
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
      var val = localStorage.getItem(isCustomKey);
      var range = localStorage.getItem(timeRangeKey) || defaultTimeRange;
      var start = localStorage.getItem(startCustomDate) || moment().format('MMMM D, YYYY');
      var end = localStorage.getItem(endCustomDate) || moment().format('MMMM D, YYYY');
      $('#reportrange span').html(start + ' - ' + end);
      if (val === 'true') {
        loadCharts(range, true, localStorage.getItem(isCustomKey), localStorage.getItem(startDateKey), localStorage.getItem(endDateKey));
      }
      else {
        $('.daterangepicker .ranges ul li[data-time=' + range + ']').trigger('click');
      }
    };
    // try adding the browser timezone to the querystring
    try {
      var timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
      baseUrl = baseUrl.replace('time=', 'timezone=' + timezone + '&time=');
      // ignore failures (older browsers do not support this)
    } catch (e) {}
    var dateTimePicker = $('.ranges li');
      dateTimePicker.click(function () {
        var timeRange = $(this).attr('data-time');
        isCustom = false;
        localStorage.setItem(isCustomKey, isCustom);
        if ($(this).attr('data-range-key') !== "Custom Range") {
          loadCharts(timeRange, true, false, localStorage.getItem(startDateKey) || moment().format('MMMM D, YYYY'), localStorage.getItem(endDateKey) || moment().format('MMMM D, YYYY'));
          localStorage.setItem(timeRangeKey, timeRange);

        // refresh every 2.5 minutes
        clearInterval(window.owChartRefresh);
        window.owChartRefresh = setInterval(loadCharts,
          1000 * 60 * 2.5,
          timeRange,
          false,
          false,
          localStorage.getItem(startDateKey),
          localStorage.getItem(endDateKey));
        }
        localStorage.setItem(timeRangeKey, timeRange);
        if($(this).attr('data-range-key') == "Custom Range") {
          var startCustom, endCustom, dateSpan;
          isCustom = true;
          localStorage.setItem(isCustomKey, isCustom);
          $("#reportrange").on('apply.daterangepicker', function (ev, picker) {
            startCustom = moment(picker.startDate.format('YYYY-MM-DD HH:mm:ss'));
            endCustom = moment(picker.endDate.format('YYYY-MM-DD HH:mm:ss'));
            dateSpan = endCustom.diff(startCustom, 'days') + 'd';
            loadCharts(dateSpan, true, true, picker.startDate.format('YYYY-MM-DD HH:mm:ss'), picker.endDate.format('YYYY-MM-DD HH:mm:ss'));
            localStorage.setItem(startDateKey, picker.startDate.format('YYYY-MM-DD HH:mm:ss'));
            localStorage.setItem(endDateKey, picker.endDate.format('YYYY-MM-DD HH:mm:ss'));
            localStorage.setItem(startCustomDate, startCustom.format('YYYY-MM-DD'));
            localStorage.setItem(endCustomDate, endCustom.format('YYYY-MM-DD'));
            localStorage.setItem(timeRangeKey, dateSpan);

        // refresh every 2.5 minutes
        clearInterval(window.owChartRefresh);
        window.owChartRefresh = setInterval(loadCharts,
          1000 * 60 * 2.5,
          dateSpan,
          false,
          true,
          localStorage.getItem(startDateKey),
          localStorage.getItem(endDateKey));
          });
        }
      });
    // bind export button
    $('#ow-chart-time a.export').click(function () {
      var time = localStorage.getItem(timeRangeKey);
      var startDate = localStorage.getItem(startDateKey);
      var endDate = localStorage.getItem(endDateKey);
      var daterange = `&start=${startDate}&end=${endDate}`;
      location.href = baseUrl + time + daterange + '&csv=1';
    });
  });
}(django.jQuery));
