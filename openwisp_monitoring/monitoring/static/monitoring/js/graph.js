(function ($) {
    'use strict';
    window.createGraph = function (data, x, id, title, type) {
        if (data === false) {
            alert(gettext('error while receiving data from server'));
            return;
        }
        if (!x) {x = data.x}
        var mode = x.length > 30 ? 'lines' : 'markers+lines',
            layout = {
                showlegend: true,
                legend: {
                    orientation: 'h',
                    xanchor: 'center',
                    yanchor: 'top',
                    y: -0.15,
                    x: 0.5,
                },
                xaxis: {visible: type != 'histogram'},
                margin: {
                  l: 50,
                  r: 50,
                  b: 15,
                  t: 20,
                  pad: 4
                },
                height: 350
            },
            graphs = [],
            container = $('#' + id),
            plotlyContainer = container.find('.js-plotly-plot').get(0),
            notApplicable = gettext('N/A'),
            unit = data.unit,
            labels = [],
            summaryLabels = [],
            help, tooltip, heading;
        if (data.colors) {
            layout.colorway = data.colors;
        }
        // given a value, returns its color and description
        // according to the color map configuration of this chart
        function findInColorMap(value) {
            var desc, color, controlVal, n,
                map = data.colorscale.map;
            if (!map) { return false };
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
        // loop over traces to put them on the graph
        for (var i=0; i<data.traces.length; i++) {
            var key = data.traces[i][0],
                label = data.traces[i][0].replace(/_/g, ' ');
            data.summary_labels && summaryLabels.push([key, data.summary_labels[i]]);
            var options = {
                    name: label,
                    type: type,
                    mode: mode,
                    fill: 'tozeroy',
                    hovertemplate: [],
                    y: []
                },
                yValuesRaw = data.traces[i][1];
            if (type != 'histogram') {
                options.x = x;
                options.hoverinfo = 'x+y';
            }
            else {
                options.x = [0];
                options.hoverinfo = 'skip';
                options.histfunc = 'sum';
            }

            if (data.colorscale) {
                var config = data.colorscale,
                    map = data.colorscale.map,
                    fixedValue = data.colorscale.fixed_value;
                options.marker = {
                    cmax: config.max,
                    cmin: config.min,
                    colorbar: {title: config.label},
                    colorscale: config.scale,
                    color: []
                }
                if (map) {
                    layout.showlegend = false;
                    layout.margin.b = 45;
                }
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
                    var mapped = findInColorMap(val);
                    // same bar length feature
                    if (typeof(fixedValue) !== undefined && val !== null) {
                        val = fixedValue
                    }
                    options.marker.color.push(mapped.color);
                    desc = mapped.desc;
                }
                // prepare data shown in chart on hover
                if (val === null) {
                    val = 0;
                    hovertemplate = notApplicable + '<extra></extra>';
                }
                else {
                    hovertemplate = shownVal + unit + '<extra>' + desc + '</extra>';
                }
                options.y.push(val);
                options.hovertemplate.push(hovertemplate);
            }
            graphs.push(options);
        }

        Plotly.newPlot(plotlyContainer, graphs, layout, {responsive: true});

        container.find('.custom-legend').remove();
        // custom legends when using color map
        if (data.colorscale && data.colorscale.map) {
            container.append('<div class="custom-legend"></div>');
            var map = data.colorscale.map,
                customLegend = container.find('.custom-legend');
            for (var i = map.length-1; i >= 0; i--) {
                var color = map[i][1],
                    label = map[i][2];
                customLegend.append(
                    '<div class="legend"><span style="background:' + color + '"></span> ' + label + '</div>'
                );
            }
        }
        container.find('.circle').remove();
        // add summary
        if (data.summary && type != 'histogram') {
            for (var i=0; i<summaryLabels.length; i++) {
                var el = summaryLabels[i],
                    key = el[0],
                    traceLabel = key.replace(/_/g, ' '),
                    label = el[1],
                    percircleOptions = {progressBarColor: data.colors[i]},
                    value = data.summary[key],
                    mapped;
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
                if (data.colorscale && data.colorscale.map) {
                    mapped = findInColorMap(value);
                    percircleOptions.progressBarColor = mapped.color;
                    label = label + ': ' + mapped.desc;
                }
                container.append(
                    '<div class="small circle" title="' + label + '"></div>'
                );
                container.find('.circle').eq(-1)
                         .percircle(percircleOptions);
            };
        }
        // do not add heading, help and tooltip if already done
        // or if there's not title and description to show
        if (container.find('h3.graph-heading').length || !data.title) {
            return;
        }
        // add heading
        container.prepend('<h3 class="graph-heading"></h3>');
        heading = container.find('.graph-heading');
        heading.text(title);
        // add help icon
        heading.append('<a class="chart-help">?</a>');
        help = heading.find('a');
        help.attr('title', gettext('Click to show chart description'))
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
