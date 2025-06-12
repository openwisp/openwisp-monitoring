"use strict";

(function ($) {
  function openFloorPlan() {
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

    renderIndoorMap();
  }

  function renderIndoorMap() {
    const graph = new NetJSONGraph(jsonPath, {
      el: "#floorplan-content",
      render: "map",

      mapOptions: {
        center: [48.577, 18.539],
        zoom: 5.5,
        zoomSnap: 0.3,
        minZoom: 3.5,
        maxZoom: 9,
        nodeConfig: {
          label: {
            offset: [0, -10],
            fontSize: "14px",
            fontWeight: "bold",
            color: "#D9644D",
          },
          animation: false,
        },
        linkConfig: { linkStyle: { width: 4 }, animation: false },
        baseOptions: {
          toolbox: {
            show: false,
          },
          media: [
            {
              query: {
                minWidth: 320,
                maxWidth: 850,
              },
              option: {
                tooltip: {
                  show: false,
                },
              },
            },
            {
              query: {
                minWidth: 851,
              },
              option: {
                tooltip: {
                  show: true,
                },
              },
            },
          ],
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

      onReady() {
        const map = this.leaflet;
        map.eachLayer((layer) => {
          if (layer._url) {
            map.removeLayer(layer);
          }
        });

        const img = new Image();
        img.src = imagePath;
        img.onload = () => {
          const aspect = img.width / img.height;
          const H = 700;
          const W = aspect * H;
          const southWest = L.latLng(53, 2);
          const swPt = map.latLngToContainerPoint(southWest);
          const nePt = swPt.add(new L.Point(W, H));
          const northEast = map.containerPointToLatLng(nePt);
          const bounds = L.latLngBounds(southWest, northEast);

          map.setMaxBounds(bounds);
          const zoomFit = map.getBoundsZoom(bounds);
          if (zoomFit <= map.getMaxZoom()) map.setZoom(zoomFit);

          L.imageOverlay(imagePath, bounds).addTo(map);

          map.invalidateSize();
          map.fitBounds(bounds);
        };
      },
    });
    graph.render();
  }

  window.openFloorPlan = openFloorPlan;
})(django.jQuery);
