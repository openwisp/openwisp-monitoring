"use strict";

(function ($) {
  const colors = window._owGeoMapConfig.STATUS_COLORS;
  function getColor(status) {
    return colors[status] || colors.unknown;
  }

  let allResults = {};
  let floors = [];
  let currentFloor = null;
  const NAV_WINDOW_SIZE = 5;
  let navWindowStart = 0;
  let selectedIndex = 0;
  let isFullScreen = false;
  let maps = {};

  async function openFloorPlan(url) {
    await fetchData(url);

    selectedIndex = floors.indexOf(currentFloor) || 0;
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

    $("#device-map-container").append($floorPlanContainer);
    $("#floorplan-container").append($floorNavigation);

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
      if (floor && allResults[floor]) {
        resolve();
        return;
      }
      $.ajax({
        url: reqUrl,
        method: "GET",
        dataType: "json",
        xhrFields: { withCredentials: true },
        success: async (data) => {
          // To make this run only one time as only in the first call floor will not be provided
          // And sort them in decreasing order so that negative floors show at the bottom and
          // positive floors at the top in floor navigation
          if (!floor) {
            floors = data.floors;
            floor = data.results[0].floor;
          }
          if (!allResults[floor]) allResults[floor] = [];
          allResults[floor] = [...allResults[floor], ...data.results];
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
      <div id="floorplan-overlay">
        <div id="floorplan-container">
          <h2 id="floorplan-heading"></h2>
          <span id="floorplan-close-btn">&times;</span>
          <div id="floorplan-content-root"></div>
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
      allResults = {};
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

    $(".left-arrow").toggleClass("disabled", selectedIndex === 0);
    $(".right-arrow").toggleClass(
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
        navWindowStart = Math.max(
          0,
          Math.min(selectedIndex - center, maxStart),
        );
        addFloorButtons(selectedIndex, navWindowStart);
        currentFloor = floors[selectedIndex];
        await showFloor(url, currentFloor);
      }
    });

    $nav.on("click", ".left-arrow:not(.disabled)", async () => {
      if (selectedIndex > 0) {
        selectedIndex--;
        const center = Math.floor(NAV_WINDOW_SIZE / 2);
        navWindowStart = Math.max(
          0,
          Math.min(selectedIndex - center, maxStart),
        );
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

    const nodesThisFloor = { nodes: allResults[floor], links: [] };

    $("#floorplan-heading").text(nodesThisFloor.nodes[0].floor_name);
    const imageUrl = nodesThisFloor.nodes[0].image;

    const root = $("#floorplan-content-root");
    root.children(".floor-content").hide();
    let $floorDiv = $(`#floor-content-${floor}`);
    if (!$floorDiv.length) {
      $floorDiv = $(
        `<div id="floor-content-${floor}" class="floor-content"></div>`,
      );
      root.append($floorDiv);
      renderIndoorMap(nodesThisFloor, imageUrl, $floorDiv[0].id);
    }
    $floorDiv.show();
    const floorNavigation = $("#floorplan-navigation");
    if (isFullScreen && maps[floor]) {
      document.exitFullscreen();
      floorNavigation.addClass("fullscreen");
      $(`#floor-content-${floor} .leaflet-container`).append(floorNavigation);
    }
    maps[currentFloor]?.invalidateSize();
  }

  let currentPopup = null;
  function loadPopUpContent(node, netjsongraphInstance) {
    const map = netjsongraphInstance.leaflet;
    if (currentPopup) {
      currentPopup.remove();
    }
    // Todo: Fix padding spacing
    const popupContent = `
    <div class="njg-tooltip-inner">
      <div class="njg-tooltip-item">
        <span class="njg-tooltip-key">name</span>
        <span class="njg-tooltip-value">${node?.device_name}</span>
      </div>
      <div class="njg-tooltip-item">
        <span class="njg-tooltip-key">Mac address</span>
        <span class="njg-tooltip-value">${node?.mac_address}</span>
      </div>
      <div class="njg-tooltip-item">
        <span class="njg-tooltip-key">status</span>
        <span class="popup-status health-${node?.monitoring.status} ">
          ${node?.monitoring.status_label}
        </span>
      </div>
      <div class="open-device-btn-container">
        <button class="default-btn open-device-btn" data-url="${node?.admin_edit_url}"">
          <span class="ow-device floor-icon"></span>
          Open Device
        </button>
      </div>
      </div>
    </div>
    `;
    $("#floorplan-container")
      .off("click", ".open-device-btn")
      .on("click", ".open-device-btn", function () {
        const url = $(this).data("url");
        window.location.href = url;
      });
    // Todo: Popup does not show when closeOnClick is true need to figure out why
    currentPopup = L.popup({ closeOnClick: false })
      .setLatLng(node?.coordinates)
      .setContent(popupContent)
      .openOn(map);
  }

  function renderIndoorMap(allResults, imageUrl, divId) {
    const indoorMap = new NetJSONGraph(allResults, {
      el: `#${divId}`,
      crs: L.CRS.Simple,
      render: "map",

      mapOptions: {
        center: [50, 50],
        zoom: 0,
        minZoom: -4,
        maxZoom: 2,
        zoomSnap: 0.5,
        zoomDelta: 0.5,
        zoomAnimation: false,
        nodeConfig: {
          label: {
            show: false,
          },
          animation: false,
          nodeStyle: (node) => ({
            radius: 9,
            color: getColor(node.properties.status),
            weight: 3,
            opacity: 1,
          }),
        },
        baseOptions: {
          media: [
            {
              option: {
                tooltip: {
                  show: false,
                },
              },
            },
          ],
        },
      },
      prepareData(data) {
        data.nodes.forEach((node) => {
          node.properties = {
            ...node.properties,
            name: node.device_name,
            status: node.monitoring.status,
            location: node.coordinates,
            "Mac address": node.mac_address,
          };
        });
        return data;
      },

      onReady() {
        const map = this.leaflet;
        maps[currentFloor] = map;
        // remove default geo map tiles
        map.eachLayer((layer) => layer._url && map.removeLayer(layer));
        const img = new Image();
        img.src = imageUrl;
        let initialZoom;
        img.onload = () => {
          const h = img.height;
          const aspectRatio = img.width / img.height;
          const w = aspectRatio * h;
          const zoom = map.getMaxZoom() - 1;
          const sw = map.unproject([0, h * 2], zoom);
          const ne = map.unproject([w * 2, 0], zoom);
          const bnds = new L.LatLngBounds(sw, ne);
          L.imageOverlay(imageUrl, bnds).addTo(map);
          map.fitBounds(bnds);
          map.setMaxBounds(bnds);
          initialZoom = map.getZoom();
          map.setView([0, 0], initialZoom);
        };
        map.on("fullscreenchange", () => {
          const floorNavigation = $("#floorplan-navigation");
          const zoomSnap = map.options.zoomSnap || 1;
          if (map.isFullscreen()) {
            map.setZoom(initialZoom + zoomSnap);
            isFullScreen = true;
            floorNavigation.addClass("fullscreen");
            $(`#floor-content-${currentFloor} .leaflet-container`).append(
              floorNavigation,
            );
          } else {
            isFullScreen = false;
            map.setZoom(initialZoom);
            floorNavigation.removeClass("fullscreen");
            $("#floorplan-container").append(floorNavigation);
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
        const nodeData = indoorMap?.data?.nodes?.find(
          (n) => n.content_object_id === deviceId,
        );
        loadPopUpContent(nodeData, indoorMap);
      },
    });
    indoorMap.render();
    window._owIndoorMap = indoorMap;
  }

  window.openFloorPlan = openFloorPlan;
})(django.jQuery);
