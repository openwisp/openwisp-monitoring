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
        for (var i=0; i<data.traces.length; i++) {
            var key = data.traces[i][0],
                label = data.traces[i][0].replace(/_/g, ' ');
            summaryLabels.push([key, data.summary_labels[i]])
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
                options['x'] = x;
                options['hoverinfo'] = 'x+y';
            }
            else {
                options['x'] = [0];
                options['hoverinfo'] = 'skip';
                options['histfunc'] = 'sum';
            }

            for (var c=0; c<yValuesRaw.length; c++) {
                var val = yValuesRaw[c],
                    hovertemplate = '%{y}' + unit + '<extra>' + label + '</extra>';
                if (val === null) {
                    val = 0;
                    hovertemplate = notApplicable + '<extra></extra>';
                }
                options.y.push(val);
                options.hovertemplate.push(hovertemplate);
            }

            graphs.push(options);
        }

        Plotly.newPlot(plotlyContainer, graphs, layout, {responsive: true});

        // do not add heading, help and tooltip if already done
        // or if there's not title and description to show
        if (container.find('h3.graph-heading').length || !data.title) {
            return;
        }
        // add summary
        if (data.summary && type != 'histogram') {
            // $.each(summaryLabels, function(i, el){
            for (var i=summaryLabels.length-1; i>=0; i--) {
                var el = summaryLabels[i],
                    key = el[0],
                    label = el[1],
                    summary, summaryText;
                summaryText = `${label}: ${data.summary[key]}${data.unit}`;
                container.prepend('<p class="summary" title="test!"></p>');
                container.find('.summary').eq(0).text(summaryText);
            };
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
