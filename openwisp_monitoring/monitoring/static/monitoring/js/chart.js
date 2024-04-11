'use strict';

(function ($) {
    function sortByTraceOrder(traceOrder, arr, propertyName){
        if (traceOrder === undefined) {
            return arr;
        }
        var newArr = [];
        for (var traceIndex=0; traceIndex<traceOrder.length; ++traceIndex) {
            for (var arrIndex=0; arrIndex<arr.length; ++arrIndex) {
                if (traceOrder[traceIndex] === arr[arrIndex][propertyName]){
                    newArr.push(arr[arrIndex]);
                    break;
                }
            }
        }
        return newArr;
    }

    function getAdaptiveScale(value, multiplier, unit) {
        if (value == 0) {
            multiplier = 1;
            unit = unit;
        } else if (value < 0.001) {
            multiplier = 1000000;
            unit = 'K' + unit;
        } else if (value < 1) {
            multiplier = 1000;
            unit = 'M' + unit;
        } else if (value < 1000) {
            multiplier = 1;
            unit = 'G' + unit;
        } else if (value >= 1000) {
            multiplier = 0.001;
            unit = 'T' + unit;
        }
        return {
            multiplier: multiplier,
            unit: unit
        };
    }

    function getAdaptiveBytes(value, multiplier) {
        return Math.round((value * multiplier) * 100) / 100;
    }

    function adaptiveFilterPoints(charts, layout, yRawVal, chartUnit = '') {
        var y = charts[0].y, sum = 0, count = 0, shownVal, average;
        for (var i=0; i < y.length; i++) {
            sum += y[i];
            if (y[i]) {
                count++;
            }
        }
        average = sum / count;
        var scales = getAdaptiveScale(average, 1, chartUnit);
        var multiplier = scales.multiplier,
            unit = scales.unit;
        for (i=0; i < y.length; i++) {
            for (var j=0; j < charts.length; j++) {
                if (yRawVal[i] == null) {
                    charts[j].hovertemplate[i] = 'N/A' + '<extra></extra>';
                    continue;
                }
                shownVal = charts[j].y[i];
                charts[j].y[i] = getAdaptiveBytes(charts[j].y[i], multiplier);
                var hoverScales = getAdaptiveScale(shownVal, 1, chartUnit);
                var hoverMultiplier = hoverScales.multiplier,
                    hoverUnit = hoverScales.unit;
                shownVal = getAdaptiveBytes(shownVal, hoverMultiplier);
                charts[j].hovertemplate[i] = shownVal + ' ' + hoverUnit;
            }
        }
        layout.yaxis.title = unit;
    }

    function adaptiveFilterSummary(i, percircles, value, chartUnit = '') {
        var scales = getAdaptiveScale(value, 1, chartUnit),
            multiplier = scales.multiplier,
            unit = scales.unit;
        value = getAdaptiveBytes(value, multiplier);
        percircles[i].text = value + ' ' + unit;
    }

    window.createChart = function (data, x, id, title, type, quickLink) {
        if (data === false) {
            alert(gettext('error while receiving data from server'));
            return;
        }
        if (!x) {x = data.x;}

        var xaxis = data.xaxis || {};
        var yaxis = data.yaxis || {};
        xaxis.visible = type != 'histogram';

        var mode = x.length > 30 ? 'lines' : 'markers+lines',
            layout = {
                showlegend: true,
                legend: {
                    orientation: 'h',
                    xanchor: 'center',
                    yanchor: 'top',
                    y: -0.15,
                    x: 0.5,
                    traceorder: 'normal'
                },
                xaxis: xaxis,
                yaxis: yaxis,
                margin: {
                  l: 50,
                  r: 50,
                  b: 15,
                  t: 20,
                  pad: 4
                },
                height: 350,
                hovermode: 'x unified'
            },
            charts = [],
            container = $('#' + id),
            plotlyContainer = container.find('.js-plotly-plot').get(0),
            notApplicable = gettext('N/A'),
            unit = data.unit,
            summaryLabels = [],
            fixedY = false,
            fixedYMax = 100,
            help, tooltip, heading;
        if (data.colors) {
            layout.colorway = data.colors;
        }
        // hide yaxis in fixed value charts
        if (data.colorscale && typeof(data.colorscale.fixed_value) !== undefined) {
            layout.yaxis = {visible: false};
        // if using %, we'll make sure the minimum y axis range is 0-100
        } else if (unit === '%') {
            fixedY = true;
        }
        if (type === 'histogram') {
            layout.hovermode = 'closest';
        }
        var map, mapped, label, fixedValue, key, chartUnit, yValues;
        // given a value, returns its color and description
        // according to the color map configuration of this chart
        function findInColorMap(value) {
            var desc, color, controlVal, n,
                map = data.colorscale.map;
            if (!map) { return false; }
            for (n in map) {
                controlVal = map[n][0];
                if (controlVal === null || value >= controlVal) {
                    color = map[n][1];
                    desc = map[n][2];
                    break;
                }
            }
            return {color: color, desc: desc};
        }
        if (data.calculate_total === true) {
            var total = data.traces[0][1].slice();
            for (i = 1; i < data.traces.length; ++i) {
                for (var j = 0; j < data.traces[i][1].length; ++j) {
                    total[j] += data.traces[i][1][j];
                }
            }
            data.traces.push(['total', total]);
            data.summary.total = Object.values(data.summary).reduce(function (a, b) {
                return a + b;
            }, 0);
        }
        // loop over traces to put them on the chart
        for (var i=0; i<data.traces.length; i++) {
            key = data.traces[i][0];
            // label for the trace, use trace_labels if available, otherwise
            // replace underscores with spaces in the key name
            label = data.trace_labels && data.trace_labels[data.traces[i][0]] || data.traces[i][0].replace(/_/g, ' ');

            if (data.summary_labels){
                if (data.trace_order) {
                    summaryLabels.push([key, data.summary_labels[data.trace_order.indexOf(key)]]);
                }
                else {
                  summaryLabels.push([key, data.summary_labels[i]]);
                }
            }
            var options = {
                    name: label,
                    type: type,
                    mode: mode,
                    fill: data.fill || 'tozeroy',
                    hovertemplate: [],
                    y: [],
                    // We use the "_key" field to sort the charts
                    // according to the order defined in "data.trace_order"
                    _key: key,
                    _connectPoints : data.connect_points || false,
                },
                yValuesRaw = data.traces[i][1];
            if (type !== 'histogram') {
                options.x = x;
                options.hoverinfo = 'x+y';
            }
            else {
                options.x = [''];
                options.histfunc = 'sum';
            }
            if (type.includes('stackedbar')) {
                layout.barmode = 'stack';
                options.type = 'bar';
                if (type === 'stackedbar+lines') {
                    if (data.trace_type[key] === 'lines') {
                        options.type = 'scatter';
                        options.mode = 'lines+markers';
                        options.line = {shape: 'hvh'};
                        options.fill = data.fill;
                    }
                    if (options._connectPoints) {
                        options.mode = 'lines';
                    }
                }
            }
            if (data.colorscale) {
                var config = data.colorscale;
                map = data.colorscale.map;
                fixedValue = data.colorscale.fixed_value;
                options.marker = {
                    cmax: config.max,
                    cmin: config.min,
                    colorbar: {title: config.label},
                    colorscale: config.scale,
                    color: []
                };
                if (map) {
                    layout.showlegend = false;
                    layout.margin.b = 45;
                }
            }

            var xValuesRaw = options.x;
            if (options._connectPoints) {
                options.x = [];
            }
            // adjust text to be displayed in Y values
            // differentiate between values with zero and no values at all (N/A)
            for (var c=0; c<yValuesRaw.length; c++) {
                var val = yValuesRaw[c],
                    shownVal = val,
                    desc = label,
                    hovertemplate;
                // if colorscale and map are supplied
                if (data.colorscale && map) {
                    mapped = findInColorMap(val);
                    // same bar length feature
                    if (typeof(fixedValue) !== undefined && val !== null) {
                        val = fixedValue;
                    }
                    options.marker.color.push(mapped.color);
                    desc = mapped.desc;
                }
                // prepare data shown in chart on hover
                if (val === null) {
                    // filter 'y' null points from options.y
                    if (options._connectPoints) {
                        continue;
                    }
                    // set data to zero on gaps unless
                    // the horizontal zeroline is hidden
                    // otherwise fills get badly drawn
                    if (layout.yaxis.zeroline !== false) {
                        val = 0;
                    }
                    hovertemplate = notApplicable + '<extra></extra>';
                }
                else {
                    hovertemplate = shownVal + unit + '<extra>' + desc + '</extra>';
                }
                // if using fixed y axis, adjust max Y value if needed
                if (fixedY && val > fixedYMax) {
                    fixedYMax = val;
                }
                options.y.push(val);
                // push only those 'x' points to options.x which has non null 'y' points
                if (options._connectPoints) {
                    options.x.push(xValuesRaw[c]);
                }
                options.hovertemplate.push(hovertemplate);
            }
            if (data.trace_order){
                options.marker = {color: data.colors[data.trace_order.indexOf(key)]};
            }
            charts.push(options);
            yValues = options.y;
        }
        charts = sortByTraceOrder(data.trace_order, charts, '_key');

        if (unit.includes('adaptive_prefix')) {
            var yRawVal;
            for (i=0; i < charts.length; i++) {
                yRawVal = data.traces[i][1];
            }
            if (data.connect_points) {
                yRawVal = yValues;
            }
            if (unit.includes('+')) {
                chartUnit = unit.split('+')[1];
            }
            adaptiveFilterPoints(charts, layout, yRawVal, chartUnit);
        }

        if (fixedY) { layout.yaxis = {range: [0, fixedYMax]}; }

        Plotly.newPlot(plotlyContainer, charts, layout, {responsive: true});

        // custom legends when using color map
        if (data.colorscale && data.colorscale.map) {
            var customLegend;
            if (container.find('.custom-legend').length) {
                customLegend = $(container.find('.percircle-container').get(0));
                customLegend.empty();
            } else {
                customLegend = $('<div class="custom-legend"></div>');
                $(container.find('.js-plotly-plot').get(0)).after(customLegend);
            }
            map = data.colorscale.map;
            for (i = map.length-1; i >= 0; i--) {
                var color = map[i][1];
                label = map[i][2];
                customLegend.append(
                    '<div class="legend"><span style="background:' + color + '"></span> ' + label + '</div>'
                );
            }
        }
        else {
            container.find('.custom-legend').remove();
        }
        // add summary
        if (data.summary && type != 'histogram') {
            var percircles = [], percircleContainer;
            if (container.find('.percircle-container').length) {
                percircleContainer = $(container.find('.percircle-container').get(0));
                percircleContainer.empty();
            } else {
                percircleContainer = $('<div class="percircle-container"></div>');
                container.append(percircleContainer);
            }
            for (i=0; i<summaryLabels.length; i++) {
                var el = summaryLabels[i],
                    percircleOptions = {
                        progressBarColor: data.colors[i],
                        // We use the "_key" field to sort the summary
                        // charts according to the order defined in "data.trace_order"
                        _key: el[0]
                    };
                key = el[0];
                percircleOptions.htmlTitle = el[1];
                var value = data.summary[key];

                if (unit === '%') {
                    percircleOptions.percent = value;
                    if (value === 0) {
                        percircleOptions.text = '0%';
                        percircleOptions.percent = 1;
                    }
                }
                else {
                    percircleOptions.text = value + data.unit;
                    percircleOptions.percent = 75;
                }
                if (value === null) {
                  percircleOptions.text = 'N/A';
                  percircleOptions.percent = 1;
                }
                if (data.colorscale && data.colorscale.map) {
                    mapped = findInColorMap(value);
                    percircleOptions.progressBarColor = mapped.color;
                    percircleOptions.htmlTitle = percircleOptions.htmlTitle + ': ' + mapped.desc;
                }
                if (data.trace_order){
                    percircleOptions.progressBarColor = data.colors[data.trace_order.indexOf(key)];
                }
                percircles.push(percircleOptions);

                if (unit.includes('adaptive_prefix')) {
                    if (unit.includes('+')) {
                        chartUnit = unit.split('+')[1];
                    }
                    adaptiveFilterSummary(i, percircles, value, chartUnit);
                }
            }
            percircles = sortByTraceOrder(data.trace_order, percircles, '_key');
            for (i=0; i<percircles.length; ++i) {
                percircleContainer.append(
                    '<div class="small circle" title="' + percircles[i].htmlTitle + '"></div>'
                );
                percircleContainer.find('.circle').eq(-1)
                         .percircle(percircles[i]);
            }
        } else {
            container.find('.percircle-container').remove();
        }
        // add quick link button
        if (quickLink) {
            if (!container.find('.quick-link-container').length){
                container.append(
                    $(
                        '<div id="'+ id + '-quick-link-container" ' +
                        'class="quick-link-container"><a href="' +
                        quickLink.url + '" class="button quick-link" id="' +
                        id + '-inline-wifisession-quick-link" title="' +
                        quickLink.title + '">' + quickLink.label  +'</a></div>')
                );
            }
        }
        // do not add heading, help and tooltip if already done
        // or if there's not title and description to show
        if (container.find('h3.chart-heading').length || !data.title) {
            return;
        }
        // add heading
        container.prepend('<h3 class="chart-heading"></h3>');
        heading = container.find('.chart-heading');
        heading.text(title);
        // add help icon
        heading.append('<a class="chart-help">?</a>');
        help = heading.find('a');
        help.attr('title', gettext('Click to show chart description'));
        // add tooltip
        container.find('.svg-container')
                 .append('<p class="tooltip"></p>');
        tooltip = container.find('p.tooltip');
        tooltip.text(data.description);
        // toggle tooltip on help click
        help.on('click', function() {
            tooltip.toggle();
        });
    };
}(django.jQuery));
