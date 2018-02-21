(function() {
    'use strict';
    window.createGraph = function(data, id, title){
        if (data === false) {
            alert(gettext('error while receiving data from server'));
            return;
        }
        var mode = data.x.length > 30 ? 'lines' : 'markers+lines',
            layout = {title: title},
            graphs = [];
        for (var i=0; i<data.graphs.length; i++) {
            graphs.push({
                name: data.graphs[i][0],
                type: 'scatter',
                mode: mode,
                x: data.x,
                y: data.graphs[i][1]
            });
        }
        Plotly.newPlot(id, graphs, layout);
    };
}());
