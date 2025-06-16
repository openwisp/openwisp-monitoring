"use strict";

(function ($) {
  function openFloorPlan(url) {
    const $floorPlanContainer = $(`
    <div id="floorplan-container">
      <span id="close-floorplan">×</span>
      <div id="floorplan-content"></div>
    </div>
  `);

    $("#device-map-container").append($floorPlanContainer);

    $("#close-floorplan").on("click", function () {
      $("#floorplan-container").remove();
    });
    $.ajax({
      url: url,
      method: "GET",
      dataType: "json",
      xhrFields: { withCredentials: true },
      success: function (data) {
        if (!data.nodes || data.nodes.length === 0) {
          $("#floorplan-content").html("<p>No floorplan data available.</p>");
          return;
        }
        // Currenlty support only one floorplan
        const firstNode = data.nodes[0];
        const image = firstNode.image;
        const netjsonData = {
          type: "NetworkGraph",
          nodes: [firstNode],
          links: [],
        };
        console.log(netjsonData);
        renderIndoorMap(netjsonData, image);
      },
      error: function () {
        alert("Error loading floorplan coordinates.");
      },
    });
  }

  function renderIndoorMap(data, image) {
    const graph = new NetJSONGraph(data, {
      el: "#floorplan-content",
      render: "map",

      mapOptions: {
        center: [30, 100],
        zoom: 1.5,
        zoomSnap: 0.3,
        minZoom: -1,
        maxZoom: 2,
        nodeConfig: {
          label: {
            offset: [0, -10],
            fontSize: "14px",
            fontWeight: "bold",
            color: "#D9644D",
          },
          animation: false,
        },
      },

      prepareData(data) {
        data.nodes.forEach((node) => {
          node.label = node.name;
          node.properties = Object.assign({}, node.properties, {
            location: node.location,
          });
        });
        return data;
      },
      // Have to find a soultion for rendering coordinates correctly here
      onReady() {
        const map = this.leaflet;
        map.eachLayer((layer) => {
          if (layer._url) map.removeLayer(layer);
        });
        const img = new Image();
        img.src = image;
        img.onload = () => {
          const w = img.width,
            h = img.height,
            bottomRight = map.unproject([0, h * 2], map.getMaxZoom() - 1),
            upperLeft = map.unproject([w * 2, 0], map.getMaxZoom() - 1),
            bounds = new L.LatLngBounds(bottomRight, upperLeft);

          L.imageOverlay(image, bounds).addTo(map);
          map.setMaxBounds(bounds);
          map.fitBounds(bounds);
        };
      },
    });
    graph.render();
  }

  window.openFloorPlan = openFloorPlan;
})(django.jQuery);
