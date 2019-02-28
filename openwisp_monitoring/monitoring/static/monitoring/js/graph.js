(function () {
    'use strict';
    window.createGraph = function (data, x, id, title) {
        if (!x) {
            x = data.x
        }
        if (data === false) {
            alert(gettext('error while receiving data from server'));
            return;
        }
        var mode = x.length > 30 ? 'lines' : 'markers+lines',
            layout = {
                title: title,
                showlegend: true,
                  legend: {
                    orientation: 'h',
                    xanchor: 'center',
                    yanchor: 'top',
                    y: -0.15,
                    x: 0.5
                }
            },
            graphs = [];
        for (var i=0; i<data.traces.length; i++) {
            var key = data.traces[i][0],
                label = data.traces[i][0].replace(/_/g, ' ');
            // add summary to label
            if (data.summary && typeof(data.summary[key]) !== undefined && data.summary[key]) {
                label = label + ' (' + data.summary[key] + ')';
            }
            graphs.push({
                name: label,
                type: 'scatter',
                mode: mode,
                fill: 'tozeroy',
                x: x,
                y: data.traces[i][1],
                hoverinfo: 'x+y',
            });
        }
        Plotly.newPlot(id, graphs, layout);
    };
}());
