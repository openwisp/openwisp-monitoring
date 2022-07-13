'use strict';
const timeRangeKey = 'ow2-chart-time-range';

django.jQuery(function ($) {
  $(document).ready(function () {
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
          beforeSend: function(){
            chartContents.hide();
            chartContents.empty();
            fallback.hide();
            if (showLoading) {
              globalLoadingOverlay.show();
            }
            localLoadingOverlay.show();
          },
          success: function(data){
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
          error: function(){
            alert('Something went wrong while loading the charts');
          },
          complete: function() {
            localLoadingOverlay.fadeOut(200, function(){
              if (showLoading) {
                globalLoadingOverlay.fadeOut(200);
              }
            });
          }
        });
      };
      setTimeout(()=>{
        var dateTimePicker = $('.ranges li');
        dateTimePicker.click(function () {
          if("Custom Range"==$(this).attr('data-range-key')) {
            return;
          }
          var timeRange = $(this).attr('data-time');
          loadCharts(timeRange, true);
          localStorage.setItem(timeRangeKey, timeRange);
          // refresh every 2.5 minutes
          clearInterval(window.owChartRefresh);
          window.owChartRefresh = setInterval(loadCharts,
            1000 * 60 * 2.5,
            timeRange,
            false);
        });
        // Function for Custom Range
        $('.drp-buttons .applyBtn').on('click', ()=> {
          setTimeout(()=>{
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
          }, 1000);
        });
      }, 1000);
    try {
      chartQuickLinks = JSON.parse($('#monitoring-chart-quick-links').html());
    } catch (error) {
      chartQuickLinks = {};
    }
    window.triggerChartLoading = function() {
      var range = localStorage.getItem(timeRangeKey) || defaultTimeRange;
      $('#ow-chart-time a[data-time=' + range + ']').trigger('click');
    };
    // try adding the browser timezone to the querystring
    try {
      var timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
      baseUrl = baseUrl.replace('time=', 'timezone=' + timezone + '&time=');
      // ignore failures (older browsers do not support this)
    } catch (e) {}
    // bind export button
    $('#ow-chart-time a.export').click(function () {
      var time = localStorage.getItem(timeRangeKey);
      location.href = baseUrl + time + '&csv=1';
    });
  });
}(django.jQuery));
