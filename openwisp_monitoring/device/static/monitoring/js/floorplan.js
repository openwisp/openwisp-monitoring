"use strict";

(function ($) {
  const status_colors = window._owGeoMapConfig.STATUS_COLORS;

  let allResults = {};
  let floors = [];
  let currentFloor = null;
  const NAV_WINDOW_SIZE = 5;
  let navWindowStart = 0;
  let selectedIndex = 0;
  let isFullScreen = false;
  let maps = {};
  let locationId = null;

  // Use case: we support overlaying two maps. The URL hash contains up to two
  // fragments separated by ';' — one is the geo map and the other is an indoor map.
  //
  // The geo map fragment has id="dashboard-geo-map". Any fragment whose id is
  // NOT "dashboard-geo-map" is treated as the indoor map fragment.
  //
  // When switching maps we expect only two maps at most; the previous map should
  // be removed before adding the new one.
  // Note: future logic to manage this will be implemented in netjsongraph.js.
  const rawUrlFragments = decodeURIComponent(window.location.hash.replace(/^#/, ""));
  const fragments = rawUrlFragments.split(";").filter((f) => f.trim() !== "");

  const indoorMapFragment = fragments.find((fragment) => {
    const params = new URLSearchParams(fragment);
    return params.get("id") !== "dashboard-geo-map";
  });

  const params = new URLSearchParams(indoorMapFragment);
  const fragmentId = params.get("id");
  // fragments format is expected to be "<locationId>:<floor>"
  const [fragmentLocationId, fragmentFloor] = fragmentId?.split(":") || [];
  if (fragmentLocationId && fragmentFloor != null) {
    const floorplanUrl = window._owGeoMapConfig.indoorCoordinatesUrl.replace(
      "000",
      fragmentLocationId,
    );
    openFloorPlan(`${floorplanUrl}`, fragmentLocationId, fragmentFloor);
  }

  async function openFloorPlan(url, id = null, floor = currentFloor) {
    locationId = id;
    await fetchData(url, floor);

    const idx = floors.indexOf(currentFloor);
    selectedIndex = idx === -1 ? 0 : idx;
    // Calculate the starting index of the navigation window so the selected floor is positioned
    // as close to the center as possible without going out of bounds.
    // Example: If selectedIndex = 3, NAV_WINDOW_SIZE = 5, floors.length = 10:
    //   center = Math.floor(5 / 2) = 2
    //   maxStart = 10 - 5 = 5
    //   navWindowStart = Math.max(0, Math.min(3 - 2, 5)) = Math.max(0, Math.min(1, 5)) = 1
    // This means we will slice floors from index 1 to 6, so the selected floor (index 3)
    // appears in the middle of the navigation window when possible.
    const maxStart = Math.max(0, floors.length - NAV_WINDOW_SIZE);
    const center = Math.floor(NAV_WINDOW_SIZE / 2);
    navWindowStart = Math.max(0, Math.min(selectedIndex - center, maxStart));

    const $floorPlanContainer = createFloorPlanContainer();
    const $floorNavigation = createFloorNavigation();

    updateBackdrop();

    $("#device-map-container").append($floorPlanContainer);
    $("#floorplan-overlay").append($floorNavigation);

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
      if (floor != null && allResults[floor]) {
        $(".floorplan-loading-spinner").hide();
        resolve();
        return;
      }
      $.ajax({
        url: reqUrl,
        method: "GET",
        dataType: "json",
        xhrFields: { withCredentials: true },
        success: async (data) => {
          const actualFloor = data.results.length ? data.results[0].floor : floor;
          if (!allResults[actualFloor]) {
            allResults[actualFloor] = [];
          }
          allResults[actualFloor] = [...allResults[actualFloor], ...data.results];
          floors = data.floors;
          if (!currentFloor && data.results.length) {
            currentFloor = actualFloor;
          }
          if (data.next) {
            await fetchData(data.next, actualFloor);
          }
          resolve();
        },
        error: () => {
          alert(gettext("Error loading floorplan coordinates."));
          $(".floorplan-loading-spinner").hide();
          reject();
        },
      });
    });
  }

  function createFloorPlanContainer() {
    return $(`
      <div id="floorplan-overlay">
        <div id="floorplan-container">
          <div id="floorplan-header">
            <h2 id="floorplan-title"></h2>
            <span id="floorplan-close-btn">&times;</span>
          </div>
          <div id="floorplan-content-root"></div>
          <div class="ow-loading-spinner floorplan-loading-spinner"></div>
        </div>
      </div>
    `);
  }

  function createFloorNavigation() {
    return $(`
      <div id="floorplan-navigation">
        <div class="nav-arrow left-arrow"></div>
        <div class="floorplan-navigation-body"></div>
        <div class="nav-arrow right-arrow"></div>
      </div>
    `);
  }

  function closeButtonHandler() {
    $("#floorplan-close-btn").on("click", () => {
      $("#floorplan-container, #floorplan-navigation").remove();
      $("#floorplan-overlay").remove();
      updateBackdrop();
      allResults = {};
      currentFloor = null;
    });
  }

  function updateBackdrop() {
    $(".menu-backdrop").toggleClass("active");
  }

  function addFloorButtons(selectedIndex, navWindowStart) {
    const $navBody = $(".floorplan-navigation-body").empty();
    const slicedFloors = floors.slice(navWindowStart, navWindowStart + NAV_WINDOW_SIZE);
    slicedFloors.forEach((floor, idx) => {
      // The index present in the floors array
      const globalIdx = navWindowStart + idx;
      $navBody.append(`
        <button class="floor-btn" data-index="${globalIdx}" data-floor="${floor}">
          ${floor}
        </button>
      `);
    });

    $(".left-arrow").toggleClass("disabled", selectedIndex === 0);
    $(".right-arrow").toggleClass("disabled", selectedIndex === floors.length - 1);

    $(".floor-btn").removeClass("active selected");
    $('.floor-btn[data-index="' + selectedIndex + '"]').addClass("active selected");
  }

  function addNavigationHandlers(url) {
    const maxStart = Math.max(0, floors.length - NAV_WINDOW_SIZE);
    const $nav = $("#floorplan-navigation");

    $nav.off("click");
    $nav.on("click", ".floor-btn", async (e) => {
      selectedIndex = +e.currentTarget.dataset.index;
      const center = Math.floor(NAV_WINDOW_SIZE / 2);
      navWindowStart = Math.max(0, Math.min(selectedIndex - center, maxStart));
      addFloorButtons(selectedIndex, navWindowStart);
      currentFloor = floors[selectedIndex];
      await showFloor(url, currentFloor);
    });

    $nav.on("click", ".right-arrow:not(.disabled)", async () => {
      if (selectedIndex < floors.length - 1) {
        selectedIndex++;
        const center = Math.floor(NAV_WINDOW_SIZE / 2);
        navWindowStart = Math.max(0, Math.min(selectedIndex - center, maxStart));
        addFloorButtons(selectedIndex, navWindowStart);
        currentFloor = floors[selectedIndex];
        await showFloor(url, currentFloor);
      }
    });

    $nav.on("click", ".left-arrow:not(.disabled)", async () => {
      if (selectedIndex > 0) {
        selectedIndex--;
        const center = Math.floor(NAV_WINDOW_SIZE / 2);
        navWindowStart = Math.max(0, Math.min(selectedIndex - center, maxStart));
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

    $(".floorplan-loading-spinner").hide();
    await fetchData(url, floor);

    const nodesThisFloor = { nodes: allResults[floor], links: [] };

    $("#floorplan-title").text(nodesThisFloor.nodes[0].floor_name);
    const imageUrl = nodesThisFloor.nodes[0].image;

    const root = $("#floorplan-content-root");
    if (isFullScreen) {
      document.exitFullscreen?.();
    }
    root.children(".floor-content").hide();
    let $floorDiv = $(`#floor-content-${floor}`);
    if (!$floorDiv.length) {
      $floorDiv = $(`<div id="floor-content-${floor}" class="floor-content"></div>`);
      root.append($floorDiv);
      renderIndoorMap(nodesThisFloor, imageUrl, $floorDiv[0].id);
    }
    $floorDiv.show();
    maps[currentFloor]?.invalidateSize();
  }

  let currentPopup = null;
  function loadPopUpContent(node, netjsongraphInstance) {
    const map = netjsongraphInstance.leaflet;
    if (currentPopup) {
      currentPopup.remove();
    }
    const popupContent = `
      <div class="njg-tooltip-inner">
        <div class="njg-tooltip-item">
          <span class="njg-tooltip-key">${gettext("name")}</span>
          <span class="njg-tooltip-value">${node?.device_name}</span>
        </div>
        <div class="njg-tooltip-item">
          <span class="njg-tooltip-key">${gettext("mac address")}</span>
          <span class="njg-tooltip-value">${node?.mac_address}</span>
        </div>
        <div class="njg-tooltip-item">
          <span class="njg-tooltip-key">${gettext("status")}</span>
          <span class="popup-status health-${node?.monitoring.status} ">
            ${gettext(node?.monitoring.status_label)}
          </span>
        </div>
        <div class="open-device-btn-container">
          <a class="default-btn open-device-btn" href="${node?.admin_edit_url}">
            <span class="ow-device floor-icon"></span>
            ${gettext("Open Device")}
          </a>
        </div>
      </div>
    `;
    // Popup does not show on closeOnClick: true (default)
    currentPopup = L.popup({
      closeOnClick: false,
    })
      .setLatLng(node?.properties.location)
      .setContent(popupContent)
      .openOn(map);
  }

  function renderIndoorMap(allResults, imageUrl, divId) {
    const indoorMap = new NetJSONGraph(allResults, {
      el: `#${divId}`,
      render: "map",
      showLabelsAtZoomLevel: 0,
      mapOptions: {
        center: [0, 0],
        zoom: 0,
        minZoom: 6,
        maxZoom: 10,
        zoomSnap: 0.5,
        zoomDelta: 0.5,
        zoomAnimation: false,
        fullscreenControl: true,
        nodeConfig: {
          label: {
            show: true,
            color: "#ffffff",
            backgroundColor: "#000000",
            borderWidth: 1,
            borderRadius: 8,
            opacity: 1,
          },
        },
        baseOptions: { media: [{ option: { tooltip: { show: false } } }] },
      },
      nodeCategories: Object.keys(status_colors).map((status) => ({
        name: status,
        nodeStyle: { color: status_colors[status] },
      })),
      prepareData(data) {
        data.nodes.forEach((node) => {
          node.properties = {
            ...node.properties,
            name: node.device_name,
            status: node.monitoring.status,
            location: node.coordinates,
            "Mac address": node.mac_address,
          };
          node.label = node.properties.name;
          node.category = node.monitoring.status;
        });
        return data;
      },

      onReady() {
        const map = this.leaflet;
        maps[floor] = indoorMap;
        // remove default geo map tiles
        map.eachLayer((layer) => layer._url && map.removeLayer(layer));
        const img = new Image();
        img.src = imageUrl;
        $(".floorplan-loading-spinner").show();
        try {
          await img.decode();
        } catch (e) {
          console.error("Failed to load floorplan image:", e);
          $(".floorplan-loading-spinner").hide();
          return;
        }
        let initialZoom;
        img.onload = () => {
          const aspectRatio = img.width / img.height;
          const h = img.height;
          const w = h * aspectRatio;
          const zoom = map.getMaxZoom() - 1;

          // To make the image center in the map at (0,0) coordinates
          const anchorLatLng = L.latLng(0, 0);
          const anchorPoint = map.project(anchorLatLng, zoom);

          // Calculate the bounds of the image, with respect to the anchor point (0, 0)
          // Leaflet's pixel coordinates increase to the right and downwards
          // Unlike cartesian system where y increases upwards
          // So top-left will have negative y and bottom-right will have positive y
          // Similarly left will have negative x and right will have positive x
          const topLeft = L.point(anchorPoint.x - w / 2, anchorPoint.y - h / 2);
          const bottomRight = L.point(anchorPoint.x + w / 2, anchorPoint.y + h / 2);

        // Update node coordinates to fit the image overlay
        // We get the node coordinates from the API in the format for L.CRS.Simple
        // So the coordinates is in for cartesian system with origin at top left corner
        // Rendering image in the third quadrant with topLeft as (0,0) and bottomRight as (w,-h)
        // So we convert py to positive and then project the point to get the corresponding topLeft
        // Then unproject the point to get the corresponding latlng on the map
        const mapOptions = this.echarts.getOption();
        const series = mapOptions.series.find((s) => s.type === "scatter");
        series.data.forEach((data, index) => {
          const node = data.node;
          const px = Number(node.coordinates.lng);
          const py = -Number(node.coordinates.lat);
          const nodeProjected = L.point(topLeft.x + px, topLeft.y + py);
          // This requires a map instance to unproject coordinates so it can't be done in prepareData
          const nodeLatLng = map.unproject(nodeProjected, zoom);
          // Also updating this.data so that after onReady when applyUrlFragmentState is called it whould
          // have the correct coordinates data points to trigger the popup at right place.
          this.data.nodes[index].location = nodeLatLng;
          this.data.nodes[index].properties.location = nodeLatLng;
          node.properties.location = nodeLatLng;
          data.value = [nodeLatLng.lng, nodeLatLng.lat];
        });
        this.echarts.setOption(mapOptions);

          // Unproject the topLeft and bottomRight points to get northWest and southEast latlngs
          const nw = map.unproject(topLeft, zoom);
          const se = map.unproject(bottomRight, zoom);
          const bnds = L.latLngBounds(nw, se);
          L.imageOverlay(imageUrl, bnds).addTo(map);
          map.fitBounds(bnds);
          map.setMaxBounds(bnds.pad(1));
          initialZoom = map.getZoom();
          map.invalidateSize();
        };

        map.on("fullscreenchange", () => {
          const floorNavigation = $("#floorplan-navigation");
          const zoomSnap = map.options.zoomSnap || 1;
          if (map.isFullscreen()) {
            map.setZoom(initialZoom + zoomSnap);
            isFullScreen = true;
            floorNavigation.addClass("fullscreen");
            $(`#floor-content-${floor} .leaflet-container`).append(
              floorNavigation,
            );
          } else {
            isFullScreen = false;
            map.setZoom(initialZoom);
            floorNavigation.removeClass("fullscreen");
            $("#floorplan-overlay").append(floorNavigation);
          }
          map.invalidateSize();
        });
      },
      onClickElement: function (type, data) {
        loadPopUpContent(data, this);
      },
    });
    indoorMap.setUtils({
      // Added to open popup for a specific location Id in selenium tests
      openPopup: function (deviceId) {
        const mapOptions = indoorMap.echarts.getOption();
        const data = mapOptions.series[0].data.find(
          (data) => data.node.device_id === deviceId,
        );
        loadPopUpContent(data?.node, indoorMap);
      },
    });
    indoorMap.render();
    $(".floorplan-loading-spinner").hide();
    window._owIndoorMap = indoorMap;
  }

  window.openFloorPlan = openFloorPlan;
})(django.jQuery);
