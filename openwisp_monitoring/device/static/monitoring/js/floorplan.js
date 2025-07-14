"use strict";

(function ($) {
  const colors = window.STATUS_COLORS;
  function getColor(status) {
    return colors[status] || colors.unknown;
  }

  let allResults = { nodes: [], links: [] };
  let floors = [];
  let currentFloor = null;
  const NAV_WINDOW_SIZE = 5;
  let navWindowStart = 0;
  let selectedIndex = 0;

  async function openFloorPlan(url) {
    await fetchData(url);

    selectedIndex = floors.indexOf(currentFloor) || 0;
    // Calculate the starting index of the navigation window so the selected floor appears near the center.
    // Example: If selectedIndex = 3 and NAV_WINDOW_SIZE = 5,
    // then navWindowStart = max(0, min(1, floors.length - 5)) => navWindowStart = 1
    // So we will slice the floors array from index 1 to 6 (1 + NAV_WINDOW_SIZE),
    // which ensures the initial floor is displayed at the center of the navigation window.
    navWindowStart = Math.max(
      0,
      Math.min(selectedIndex - 2, floors.length - NAV_WINDOW_SIZE),
    );

    const $floorPlanContainer = createFloorPlanContainer();
    const $floorNavigation = createFloorNavigation();

    $("#device-map-container").append($floorPlanContainer);
    $floorPlanContainer.append($floorNavigation);

    closeButtonHandler();
    addFloorButtons(selectedIndex, navWindowStart);
    addNavigationHandlers(url);
    await showFloor(url, currentFloor);
  }

  function fetchData(url, floor = null) {
    const reqUrl = floor ? `${url}?floor=${floor}` : url;
    return new Promise((resolve, reject) => {
      // If data for the requested floor already exists in allResults,
      // skip the API call to avoid redundant requests.
      if (floor && allResults.nodes.some((n) => n.floor === floor)) {
        resolve();
        return;
      }
      $.ajax({
        url: reqUrl,
        method: "GET",
        dataType: "json",
        xhrFields: { withCredentials: true },
        success: async (data) => {
          if (!floor) floors = data.floors.sort((a, b) => b - a);
          allResults = {
            ...allResults,
            nodes: [...allResults.nodes, ...data.results],
          };
          if (!currentFloor && data.results.length) {
            currentFloor = data.results[0].floor;
          }
          if (data.next) {
            await fetchData(data.next);
          }
          resolve();
        },
        error: () => {
          alert("Error loading floorplan coordinates.");
          reject();
        },
      });
    });
  }

  function createFloorPlanContainer() {
    return $(`
      <div id="floorplan-container">
        <h2 id="floorplan-heading"></h2>
        <span id="floorplan-close-btn">&times;</span>
        <div id="floorplan-content-root"></div>
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

  function closeButtonHandler() {
    $("#floorplan-close-btn").on("click", () => {
      $("#floorplan-container, #floorplan-navigation").remove();
    });
  }

  function addFloorButtons(selectedIndex, navWindowStart) {
    const $navBody = $(".floorplan-navigation-body").empty();
    const slicedFloors = floors.slice(
      navWindowStart,
      navWindowStart + NAV_WINDOW_SIZE,
    );
    slicedFloors.forEach((floor, idx) => {
      // The index present in the floors array
      const globalIdx = navWindowStart + idx;
      $navBody.append(`
        <button class="floor-btn" data-index="${globalIdx}" data-floor="${floor}">
          ${floor}
        </button>
      `);
    });

    $(".up-arrow").toggleClass("disabled", selectedIndex === 0);
    $(".down-arrow").toggleClass(
      "disabled",
      selectedIndex === floors.length - 1,
    );

    $(".floor-btn").removeClass("active selected");
    $('.floor-btn[data-index="' + selectedIndex + '"]').addClass(
      "active selected",
    );
  }

  function addNavigationHandlers(url) {
    const maxStart = Math.max(0, floors.length - NAV_WINDOW_SIZE);
    const $nav = $("#floorplan-navigation");

    $nav.off("click");
    $nav.on("click", ".floor-btn", async (e) => {
      selectedIndex = +e.currentTarget.dataset.index;
      addFloorButtons(selectedIndex, navWindowStart);
      currentFloor = floors[selectedIndex];
      await showFloor(url, currentFloor);
    });

    $nav.on("click", ".down-arrow:not(.disabled)", async () => {
      if (selectedIndex < floors.length - 1) {
        selectedIndex++;
        if (selectedIndex >= navWindowStart + NAV_WINDOW_SIZE) {
          navWindowStart = Math.min(navWindowStart + 1, maxStart);
        }
        addFloorButtons(selectedIndex, navWindowStart);
        currentFloor = floors[selectedIndex];
        await showFloor(url, currentFloor);
      }
    });

    $nav.on("click", ".up-arrow:not(.disabled)", async () => {
      if (selectedIndex > 0) {
        selectedIndex--;
        if (selectedIndex < navWindowStart) {
          navWindowStart = Math.max(navWindowStart - 1, 0);
        }
        addFloorButtons(selectedIndex, navWindowStart);
        currentFloor = floors[selectedIndex];
        await showFloor(url, currentFloor);
      }
    });
  }

  async function showFloor(url, floor) {
    $("#floorplan-navigation .floor-btn")
      .removeClass("active selected")
      .filter(`[data-floor="${floor}"]`)
      .addClass("active selected");

    await fetchData(url, floor);

    const nodesThisFloor = allResults.nodes.filter((n) => n.floor === floor);
    $("#floorplan-heading").text(nodesThisFloor[0].floor_name);

    const imageUrl = nodesThisFloor[0].image;
    const filtered = { ...allResults, nodes: nodesThisFloor };

    const root = $("#floorplan-content-root");
    root.children(".floor-content").hide();
    let $floorDiv = $(`#floor-content-${floor}`);
    if (!$floorDiv.length) {
      $floorDiv = $(
        `<div id="floor-content-${floor}" class="floor-content"></div>`,
      );
      root.append($floorDiv);
      renderIndoorMap(filtered, imageUrl, $floorDiv[0].id);
    }
    $floorDiv.show();
  }

  let graph;
  function renderIndoorMap(allResults, imageUrl, divId) {
    graph = new NetJSONGraph(allResults, {
      el: `#${divId}`,
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
            status: "critical",
            location: node.coordinates,
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
        };
      },
    });

    graph.render();
  }

  window.openFloorPlan = openFloorPlan;
})(django.jQuery);
