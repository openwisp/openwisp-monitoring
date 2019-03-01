(function () {
    'use strict';
    window.createGraph = function (data, x, id, title, type) {
        if (data === false) {
            alert(gettext('error while receiving data from server'));
            return;
        }
        if (!x) {x = data.x}
        var mode = x.length > 30 ? 'lines' : 'markers+lines',
            layout = {
                title: title,
                showlegend: true,
                legend: {
                    orientation: 'h',
                    xanchor: 'center',
                    yanchor: 'top',
                    y: -0.15,
                    x: 0.5,
                },
                xaxis: {visible: type == 'line'}
            },
            graphs = [],
            typeMap = {
                'line': 'scatter',
                'histogram': 'histogram'
            };
        for (var i=0; i<data.traces.length; i++) {
            var key = data.traces[i][0],
                label = data.traces[i][0].replace(/_/g, ' ');
            // add summary to label
            if (
              data.summary &&
              typeof(data.summary[key]) !== undefined &&
              data.summary[key] !== null && type == 'line'
            ) {
                label = label + ' (' + data.summary[key] + ')';
            }
            var options = {
                name: label,
                type: typeMap[type],
                mode: mode,
                y: data.traces[i][1],
                fill: 'tozeroy',
            };
            if (type == 'line') {
                options['x'] = x;
                options['hoverinfo'] = 'x+y';
            }
            else if (type == 'histogram') {
                options['x'] = [0];
                options['hoverinfo'] = 'skip';
                options['histfunc'] = 'sum';
            }
            graphs.push(options);
        }
        Plotly.newPlot(id, graphs, layout);
    };
}());
