(function () {
    'use strict';
    window.createGraph = function (data, id, title) {
        if (data === false) {
            alert(gettext('error while receiving data from server'));
            return;
        }
        var mode = data.x.length > 30 ? 'lines' : 'markers+lines',
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
        for (var i=0; i<data.graphs.length; i++) {
            var key = data.graphs[i][0],
                label = data.graphs[i][0].replace(/_/g, ' ');
            // add summary to label
            if (data.summary && typeof(data.summary[key]) !== undefined) {
                label = label + ' (' + data.summary[key] + ')';
            }
            graphs.push({
                name: label,
                type: 'scatter',
                mode: mode,
                fill: 'tozeroy',
                x: data.x,
                y: data.graphs[i][1],
                hoverinfo: 'x+y',
            });
        }
        Plotly.newPlot(id, graphs, layout);
    };
}());
