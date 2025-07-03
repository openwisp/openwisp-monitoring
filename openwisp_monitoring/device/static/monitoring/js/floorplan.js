"use strict";

(function ($) {
  const colors = {
    ok: "#267126",
    problem: "#ffb442",
    critical: "#a72d1d",
    unknown: "#353c44",
    deactivated: "#0000",
  };
  function getColor(status) {
    return colors[status] || colors.unknown;
  }
  function createFloorPlanContainer() {
    return $(`
      <div id="floorplan-container">
        <h2 id="floorplan-heading"></h2>
        <span id="floorplan-close-btn">&times;</span>
        <div id="floorplan-content"></div>
      </div>
    `);
  }

  function createFloorNavigation() {
    return $(`
      <div id="floorplan-navigation">
        <div class="nav-arrow up-arrow"></div>
        <div class="floorplan-navigation-body"></div>
        <div class="nav-arrow down-arrow"></div>
      </div>
    `);
  }

  function bindCloseHandler() {
    $("#floorplan-close-btn").on("click", () => {
      $("#floorplan-container, #floorplan-navigation").remove();
    });
  }

  const NAV_WINDOW_SIZE = 4;
  let navWindowStart = 0;
  let selectedIndex = 0;

  function buildFloorButtons(data) {
    const floors = data.available_floors;
    const $navBody = $(".floorplan-navigation-body").empty();
    const maxStart = Math.max(0, floors.length - NAV_WINDOW_SIZE);
    navWindowStart = Math.min(navWindowStart, maxStart);

    const windowFloors = floors.slice(
      navWindowStart,
      navWindowStart + NAV_WINDOW_SIZE
    );
    windowFloors.forEach((floor, idx) => {
      const globalIdx = navWindowStart + idx;
      $navBody.append(`
        <button class="floor-btn" data-index="${globalIdx}" data-floor="${floor}">
          ${floor}
        </button>
      `);
    });

    $(".up-arrow").toggleClass("disabled", selectedIndex === 0);
    $(".down-arrow").toggleClass("disabled", selectedIndex === floors.length - 1);

    $(".floor-btn").removeClass("active selected");
    $('.floor-btn[data-index="' + selectedIndex + '"]').addClass("active selected");
  }

  function bindNavigationHandlers(data) {
    const floors = data.available_floors;
    const maxStart = Math.max(0, floors.length - NAV_WINDOW_SIZE);
    const $nav = $("#floorplan-navigation");

    $nav.off("click");
    $nav.on("click", ".floor-btn", (e) => {
      selectedIndex = +$(e.currentTarget).data("index");
      adjustWindowAndShow(data);
    });

    $nav.on("click", ".down-arrow:not(.disabled)", () => {
      if (selectedIndex < floors.length - 1) {
        selectedIndex++;
        if (selectedIndex >= navWindowStart + NAV_WINDOW_SIZE) {
          navWindowStart = Math.min(navWindowStart + 1, maxStart);
        }
        adjustWindowAndShow(data);
      }
    });

    $nav.on("click", ".up-arrow:not(.disabled)", () => {
      if (selectedIndex > 0) {
        selectedIndex--;
        if (selectedIndex < navWindowStart) {
          navWindowStart = Math.max(navWindowStart - 1, 0);
        }
        adjustWindowAndShow(data);
      }
    });
  }

  function adjustWindowAndShow(data) {
    buildFloorButtons(data);
    const floors = data.available_floors;
    const floorNum = floors[selectedIndex];
    showFloor(data, floorNum);
  }

  function showFloor(data, floorNum) {
    $("#floorplan-navigation .floor-btn")
      .removeClass("active selected")
      .filter(`[data-floor="${floorNum}"]`)
      .addClass("active selected");

    $("#floorplan-heading")
      .text(data.nodes.find((n) => n.floor === floorNum).floor_name)
      .data("floor", floorNum);

    const nodesThisFloor = data.nodes.filter((n) => n.floor === floorNum);
    if (!nodesThisFloor.length) return;

    const imageUrl = nodesThisFloor[0].image;
    const filtered = { ...data, nodes: nodesThisFloor };

    $("#floorplan-content").replaceWith(`<div id="floorplan-content"></div>`);

    renderIndoorMap(filtered, imageUrl);
  }

  function renderIndoorMap(data, imageUrl) {
    const graph = new NetJSONGraph(data, {
      el: "#floorplan-content",
      crs: L.CRS.Simple,
      render: "map",

      mapOptions: {
        center: [50, 50],
        zoom: 1,
        minZoom: -1,
        maxZoom: 2,
        nodeConfig: {
          label: {
            show: false,
          },
          animation: false,
          nodeStyle: (node) => ({
            radius: 9,
            color: getColor(node.properties.status),
            weight: 3,
            opacity: 0.7,
          }),
        },
        baseOptions: { media: [{ option: { tooltip: { show: true } } }] },
      },

      prepareData(data) {
        data.nodes.forEach((node) => {
          // To hide DeviceLocation id in tooltip
          node.id = "";
          node.properties = {
            ...node.properties,
            name: node.device_name,
            status: "ok",
            location: node.location,
            "Mac address": node.mac_address,
          };
        });
        return data;
      },

      onReady() {
        const map = this.leaflet;
        // remove default geo map tiles
        map.eachLayer((layer) => layer._url && map.removeLayer(layer));
        const img = new Image();
        img.src = imageUrl;
        img.onload = () => {
          const w = img.width;
          const h = img.height;
          const zoom = map.getMaxZoom() - 1;
          const sw = map.unproject([0, h * 2], zoom);
          const ne = map.unproject([w * 2, 0], zoom);
          const bnds = new L.LatLngBounds(sw, ne);
          L.imageOverlay(imageUrl, bnds).addTo(map);
          map.fitBounds(bnds);
          map.setMaxBounds(bnds);
          map.setView([0, 0], 0);
        };
      },
    });

    graph.render();
  }

  function onAjaxSuccess(data) {
    if (data.nodes.length === 0) {
      alert("No floorplans added for this location.");
      return;
    }

    const $floorPlanContainer = createFloorPlanContainer();
    const $floorNavigation = createFloorNavigation();

    $("#device-map-container").append($floorPlanContainer);
    $floorPlanContainer.append($floorNavigation);

    bindCloseHandler();
    buildFloorButtons(data);
    bindNavigationHandlers(data);

    showFloor(data, data.nodes[0].floor);
  }

  function openFloorPlan(url) {
    $.ajax({
      url,
      method: "GET",
      dataType: "json",
      xhrFields: { withCredentials: true },
      success: (data) => onAjaxSuccess(data),
      error: () => alert("Error loading floorplan coordinates."),
    });
  }

  window.openFloorPlan = openFloorPlan;
})(django.jQuery);
