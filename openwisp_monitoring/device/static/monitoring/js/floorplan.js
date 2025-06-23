"use strict";

(function ($) {
  function openFloorPlan(url) {
    const $floorPlanContainer = $(`
      <div id="floorplan-container">
        <span id="floorplan-close-btn">×</span>
        <div id="floorplan-content"></div>
      </div>
    `);

    const $floorNavigation = $(`
      <div id="floorplan-navigation">
        <div class="nav-arrow up-arrow"></div>
        <div class="floorplan-navigation-body"></div>
        <div class="nav-arrow down-arrow"></div>
      </div>
    `);

    $("#device-map-container").append($floorPlanContainer, $floorNavigation);

    $("#floorplan-close-btn").on("click", function () {
      $("#floorplan-container").remove();
      $("#floorplan-navigation").remove();
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

        const floors = [...new Set(data.nodes.map((n) => n.floor))].sort(
          (a, b) => a - b,
        );

        const $navBody = $floorNavigation
          .find(".floorplan-navigation-body")
          .empty();

        floors.forEach((floorNum) => {
          $navBody.append(`
            <button class="floor-btn" data-floor="${floorNum}">
              ${floorNum}
            </button>
          `);
        });

        $floorNavigation
          .off("click", ".floor-btn")
          .on("click", ".floor-btn", (e) => {
            const floor = +$(e.currentTarget).data("floor");
            showFloor(floor);
          });

        showFloor(floors[0]);

        function showFloor(floorNum) {
          const nodesThisFloor = data.nodes.filter((n) => n.floor === floorNum);
          if (nodesThisFloor.length === 0) return;

          const image = nodesThisFloor[0].image;
          const netjsonData = {
            type: "NetworkGraph",
            nodes: nodesThisFloor,
            links: [],
          };

          $("#floorplan-content").replaceWith(
            `<div id="floorplan-content"></div>`,
          );

          renderIndoorMap(netjsonData, image);
        }
      },
      error: function () {
        alert("Error loading floorplan coordinates.");
      },
    });
  }

  function renderIndoorMap(data, imageUrl) {
    const graph = new NetJSONGraph(data, {
      el: "#floorplan-content",
      render: "map",
      mapOptions: {
        center: [50, 50],
        zoom: 1,
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

      onReady() {
        const map = this.leaflet;
        const image = new Image();
        image.src = imageUrl;

        image.onload = function () {
          const aspectRatio = image.width / image.height;
          const h = image.height;
          const w = image.width;
          const zoom = map.getMaxZoom() - 1;
          const bottomRight = map.unproject([0, h * 2], zoom);
          const upperLeft = map.unproject([w * 2, 0], zoom);
          const bounds = new L.LatLngBounds(bottomRight, upperLeft);

          L.imageOverlay(imageUrl, bounds).addTo(map);
          map.fitBounds(bounds);
          map.setMaxBounds(bounds);
          map.setView([0, 0], 0.25);
        };

        // Remove base tile layers
        map.eachLayer((layer) => {
          if (layer._url) {
            map.removeLayer(layer);
          }
        });
      },
    });

    graph.render();
  }

  window.openFloorPlan = openFloorPlan;
})(django.jQuery);
