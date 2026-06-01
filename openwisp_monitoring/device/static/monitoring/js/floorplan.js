"use strict";

(function ($) {
  const status_colors = window._owGeoMapConfig.STATUS_COLORS;
  const NAV_WINDOW_SIZE = 5;

  function getFloorplanState() {
    const $overlay = $("#floorplan-overlay");
    if (!$overlay.length) return null;
    return $overlay.data("floorplanState") || null;
  }

  function setFloorplanState(nextState) {
    $("#floorplan-overlay").data("floorplanState", nextState);
  }

  const escapeHtml = function (text) {
    if (!text) return "";
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  };

  function buildInitialFloorplanState(url, id, floor) {
    return {
      state: { url: String(url), locationId: id, currentFloor: floor },
      allResults: {},
      floors: [],
      maps: {},
      navWindowStart: 0,
      selectedIndex: 0,
      isFullScreen: false,
      // Used to ignore late ajax responses from older sessions.
      _sessionId: window.crypto.randomUUID(),
    };
  }

  // Use case: we support overlaying two maps. The URL hash contains up to two
  // fragments separated by ';' — one is the geo map and the other is an indoor map.
  //
  // The geo map fragment has id="dashboard-geo-map". Any fragment whose id is
  // NOT "dashboard-geo-map" is treated as the indoor map fragment.
  //
  // When switching maps we expect only two maps at most; the previous map should
  // be removed before adding the new one.
  // Note: future logic to manage this will be implemented in netjsongraph.js.
  function getIndoorMapIdFromUrl() {
    const rawUrlFragments = decodeURIComponent(window.location.hash.replace(/^#/, ""));
    const fragments = rawUrlFragments.split(";").filter((f) => f.trim() !== "");
    const indoorFragment = fragments.find((fragment) => {
      const params = new URLSearchParams(fragment);
      const id = params.get("id");
      // "dashboard-geo-map" is bookmarkableActions.id for geo map
      return id && id !== "dashboard-geo-map";
    });
    if (!indoorFragment) {
      return null;
    }
    const params = new URLSearchParams(indoorFragment);
    const fragmentId = params.get("id");
    // fragments format is expected to be "<locationId>_<floor>"
    const [fragmentLocationId, fragmentFloor] = fragmentId?.split("_") || [];
    if (!fragmentLocationId || fragmentFloor == null) {
      return null;
    }
    return { fragmentLocationId, fragmentFloor };
  }

  // Initialize floorplan on page load if URL contains indoor map fragment
  const indoorMapId = getIndoorMapIdFromUrl();
  if (indoorMapId) {
    const { fragmentLocationId, fragmentFloor } = indoorMapId;
    const floorplanUrl = window._owGeoMapConfig.indoorCoordinatesUrl.replace(
      "000",
      fragmentLocationId,
    );
    openFloorPlan(floorplanUrl, fragmentLocationId, fragmentFloor);
  }

  function calculateNavigationState(currentFloor) {
    const floorplanState = getFloorplanState();
    if (!floorplanState) return;
    const idx = floorplanState.floors.indexOf(currentFloor);
    floorplanState.selectedIndex = idx === -1 ? 0 : idx;
    const maxStart = Math.max(0, floorplanState.floors.length - NAV_WINDOW_SIZE);
    const center = Math.floor(NAV_WINDOW_SIZE / 2);
    floorplanState.navWindowStart = Math.max(
      0,
      Math.min(floorplanState.selectedIndex - center, maxStart),
    );
    setFloorplanState(floorplanState);
  }

  async function openFloorPlan(url, id, floor = null) {
    if (id == null) {
      throw new Error("openFloorPlan requires a locationId");
    }
    if (document.getElementById("floorplan-overlay")) {
      destroyFloorplan();
    }

    // Create UI first so we have a stable place to store state via $.data().
    const $floorPlanContainer = createFloorPlanContainer();
    const $floorNavigation = createFloorNavigation();
    $(".menu-backdrop").addClass("active");
    $("#dashboard-map-overlay").append($floorPlanContainer);
    $("#floorplan-overlay").append($floorNavigation);

    setFloorplanState(buildInitialFloorplanState(url, id, floor));

    await fetchData(url, floor);
    const floorplanState = getFloorplanState();
    if (!floorplanState?.state) return;
    calculateNavigationState(floorplanState.state.currentFloor);

    addFloorButtons();
    await showFloor(url, floorplanState.state.currentFloor);
  }

  function fetchData(url, floor = null) {
    const floorplanState = getFloorplanState();
    if (!floorplanState?.allResults) return Promise.resolve();
    const reqUrl = new URL(url, window.location.origin);
    // Prevent adding params if already exists
    if (floor != null && !reqUrl.searchParams.has("floor")) {
      reqUrl.searchParams.set("floor", floor);
    }
    const capturedSessionId = floorplanState._sessionId;
    return new Promise((resolve, reject) => {
      // If data for the requested floor already exists in allResults,
      // skip the API call to avoid redundant requests.
      if (floor != null && floorplanState.allResults[floor]) {
        $(".floorplan-loading-spinner").hide();
        resolve();
        return;
      }
      $.ajax({
        url: reqUrl.toString(),
        method: "GET",
        dataType: "json",
        xhrFields: { withCredentials: true },
        success: async (data) => {
          const floorplanState = getFloorplanState();
          if (
            !floorplanState?.allResults ||
            floorplanState._sessionId !== capturedSessionId
          ) {
            resolve();
            return;
          }
          try {
            const actualFloor = data.results.length ? data.results[0].floor : floor;
            if (!floorplanState.allResults[actualFloor]) {
              floorplanState.allResults[actualFloor] = [];
            }
            floorplanState.allResults[actualFloor] = [
              ...floorplanState.allResults[actualFloor],
              ...data.results,
            ];
            floorplanState.floors = data.floors;
            if (!floorplanState.state.currentFloor && data.results.length) {
              floorplanState.state.currentFloor = actualFloor;
            }
            setFloorplanState(floorplanState);
            if (data.next) {
              await fetchData(data.next, actualFloor);
            }
            resolve();
          } catch (e) {
            alert(gettext("Error loading floorplan coordinates."));
            $(".floorplan-loading-spinner").hide();
            reject(e);
          }
        },
        error: (xhr, status, err) => {
          alert(gettext("Error loading floorplan coordinates."));
          $(".floorplan-loading-spinner").hide();
          reject(new Error(`${status}: ${err}`));
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

  function destroyFloorplan() {
    const floorplanState = getFloorplanState();
    if (floorplanState?.maps) {
      Object.values(floorplanState.maps).forEach((indoorMap) => {
        if (indoorMap.leaflet) {
          indoorMap.leaflet.off("fullscreenchange");
          indoorMap.leaflet.remove();
        }
        if (indoorMap.echarts) {
          indoorMap.echarts.dispose();
        }
      });
    }

    // Remove DOM and state first — ensures fragmentchange handler
    // sees overlay is closed and doesn't re-trigger destroyFloorplan.
    $("#floorplan-container, #floorplan-navigation").remove();
    $("#floorplan-overlay").removeData("floorplanState");
    $("#floorplan-overlay").remove();
    $(".menu-backdrop").removeClass("active");

    // Strip any indoor fragment from the URL using direct replaceState,
    // avoiding the library's updateUrlFragments (which dispatches fragmentchange).
    const raw = window.location.hash.replace(/^#/, "");
    if (raw) {
      const fragments = decodeURIComponent(raw)
        .split(";")
        .map((f) => f.trim())
        .filter(Boolean);
      if (fragments.length) {
        const kept = fragments.filter((fragment) => {
          const params = new URLSearchParams(fragment);
          return params.get("id") === "dashboard-geo-map";
        });
        const nextHash = kept.length ? `#${encodeURIComponent(kept.join(";"))}` : "";
        const nextUrl = `${window.location.pathname}${window.location.search}${nextHash}`;
        window.history.replaceState(null, "", nextUrl);
      }
    }
  }

  function addFloorButtons() {
    const floorplanState = getFloorplanState();
    if (!floorplanState) return;
    const $navBody = $(".floorplan-navigation-body").empty();
    const slicedFloors = floorplanState.floors.slice(
      floorplanState.navWindowStart,
      floorplanState.navWindowStart + NAV_WINDOW_SIZE,
    );
    slicedFloors.forEach((floor, idx) => {
      // The index present in the floors array
      const globalIdx = floorplanState.navWindowStart + idx;
      $navBody.append(`
        <button class="floor-btn" data-index="${globalIdx}" data-floor="${floor}">
          ${floor}
        </button>
      `);
    });

    $(".left-arrow").toggleClass("disabled", floorplanState.selectedIndex === 0);
    $(".right-arrow").toggleClass(
      "disabled",
      floorplanState.selectedIndex === floorplanState.floors.length - 1,
    );
    $(".floor-btn").removeClass("active selected");
    $('.floor-btn[data-index="' + floorplanState.selectedIndex + '"]').addClass(
      "active selected",
    );
  }

  async function showFloor(url, floor) {
    const floorplanState = getFloorplanState();
    if (!floorplanState?.state) return;

    await fetchData(url, floor);
    const nextState = getFloorplanState();
    if (!nextState?.state) return;

    const nodesThisFloor = { nodes: nextState.allResults[floor], links: [] };
    if (!nodesThisFloor.nodes || nodesThisFloor.nodes.length === 0) {
      $(".floorplan-loading-spinner").hide();
      console.warn(`No data available for floor "${floor}".`);
      return;
    }

    $("#floorplan-title").text(nodesThisFloor.nodes[0].floor_name);
    const imageUrl = nodesThisFloor.nodes[0].image;

    const root = $("#floorplan-content-root");
    if (nextState.isFullScreen) {
      document.exitFullscreen?.();
    }
    root.children(".floor-content").hide();
    let $floorDiv = $(`#floor-content-${floor}`);
    if (!$floorDiv.length) {
      $floorDiv = $(`<div id="floor-content-${floor}" class="floor-content"></div>`);
      root.append($floorDiv);
      renderIndoorMap(imageUrl, $floorDiv[0].id, floor);
    } else {
      $(".floorplan-loading-spinner").hide();
    }
    $floorDiv.show();
    nextState.maps[nextState.state.currentFloor]?.leaflet?.invalidateSize();
    // Since the div containing the indoor map is saved after the first render
    // and later floors are shown or hidden instead of re-rendered, onReady is not
    // triggered again. Therefore we need to push the URL fragment manually
    // when switching floors.
    pushIndoorMapIdFragment(nextState.maps[nextState.state.currentFloor], floor);
  }

  function pushIndoorMapIdFragment(indoorMap, floor, replace = true) {
    if (!indoorMap) {
      return;
    }
    const floorplanState = getFloorplanState();
    if (!floorplanState?.state) return;
    const fragments = indoorMap?.utils?.parseUrlFragments();
    const indoorMapId = indoorMap?.config?.bookmarkableActions?.id;
    if (!fragments || !indoorMapId) {
      return;
    }
    const indoorParams = fragments[indoorMapId] || new URLSearchParams();
    indoorParams.set("id", `${floorplanState.state.locationId}_${floor}`);
    fragments[indoorMapId] = indoorParams;
    indoorMap?.utils?.updateUrlFragments(fragments, null, replace);
  }

  function loadPopUpContent(node, netjsongraphInstance) {
    const popupContent = `
      <div class="njg-tooltip-inner">
        <div class="njg-tooltip-item">
          <span class="njg-tooltip-key">${gettext("name")}</span>
          <span class="njg-tooltip-value">${escapeHtml(node?.device_name)}</span>
        </div>
        <div class="njg-tooltip-item">
          <span class="njg-tooltip-key">${gettext("mac address")}</span>
          <span class="njg-tooltip-value">${escapeHtml(node?.mac_address)}</span>
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
    return popupContent;
  }

  function renderIndoorMap(imageUrl, divId, floor) {
    const indoorMap = new NetJSONGraph(
      { nodes: (getFloorplanState()?.allResults || {})[floor], links: [] },
      {
        el: `#${divId}`,
        render: "map",
        showMapLabelsAtZoom: 0,
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
          nodePopup: {
            show: true,
            content: loadPopUpContent,
            config: {
              closeOnClick: false,
              autoPan: true,
              autoPanPadding: [25, 25],
              offset: null,
            },
          },
        },
        bookmarkableActions: {
          enabled: true,
          id: `${getFloorplanState()?.state?.locationId}_${floor}`,
          zoomOnRestore: false,
          preserveFragment: true,
        },
        nodeCategories: Object.keys(status_colors).map((status) => ({
          name: status,
          nodeStyle: { color: status_colors[status] },
        })),
        prepareData(data) {
          data.nodes.forEach((node) => {
            node.location = node.coordinates;
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

        async onReady() {
          const floorplanState = getFloorplanState();
          if (!floorplanState?.state) return;
          // Guard against stale async continuation if the overlay is closed or a
          // newer floorplan session replaces the current one while awaiting.
          const sessionId = floorplanState._sessionId;
          const map = this.leaflet;
          floorplanState.maps[floor] = indoorMap;
          setFloorplanState(floorplanState);
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

          const latestState = getFloorplanState();
          if (
            !latestState?.state ||
            latestState._sessionId !== sessionId ||
            latestState.maps[floor] !== indoorMap
          ) {
            // Don't touch map/echarts/DOM: this continuation is stale.
            return;
          }
          const isActiveFloor = latestState.state.currentFloor === floor;
          let initialZoom;
          const h = img.height;
          const w = h * (img.width / img.height);
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
            // Also updating this.data so that after onReady when applyUrlFragmentState is called it would
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
          if (isActiveFloor) {
            $(".floorplan-loading-spinner").hide();
          }
          map.on("fullscreenchange", () => {
            const floorplanState = getFloorplanState();
            if (!floorplanState?.state) return;
            const floorNavigation = $("#floorplan-navigation");
            const zoomSnap = map.options.zoomSnap || 1;
            if (map.isFullscreen()) {
              map.setZoom(initialZoom + zoomSnap);
              floorplanState.isFullScreen = true;
              floorNavigation.addClass("fullscreen");
              $(`#floor-content-${floor} .leaflet-container`).append(floorNavigation);
            } else {
              floorplanState.isFullScreen = false;
              map.setZoom(initialZoom);
              floorNavigation.removeClass("fullscreen");
              $("#floorplan-overlay").append(floorNavigation);
            }
            setFloorplanState(floorplanState);
            map.invalidateSize();
          });
          // Push the indoor map fragment id=<locationId>:<floor> to the URL once the map
          // instance is ready, so the indoor map can be opened directly from the URL
          // without requiring a node click to add the fragment.
          if (isActiveFloor) {
            pushIndoorMapIdFragment(this, floor);
          }
        },
        // Popup handling is delegated to nodePopup.content,
        // so disable the default onClickElement popup behavior.
        onClickElement: function () {},
      },
    );
    indoorMap.setUtils({
      // Added a utility function to open a specific popup for a device Id in selenium tests
      openPopup: function (deviceId) {
        const index = indoorMap?.data?.nodes?.findIndex(
          (n) => n.device_id === deviceId,
        );
        const nodeData = indoorMap?.data?.nodes?.[index];
        if (index === -1 || !nodeData) {
          const id = indoorMap.config.bookmarkableActions.id;
          indoorMap.utils.removeUrlFragment(id);
          console.error(`Node with ID "${deviceId}" not found.`);
          return;
        }
        const option = indoorMap.echarts.getOption();
        const series = option.series.find((s) => s.type === "scatter");
        const seriesIndex = option.series.indexOf(series);

        const params = {
          componentType: "series",
          componentSubType: series.type,
          dataIndex: index,
          data: {
            ...series.data[index],
            node: nodeData,
          },
          seriesIndex: seriesIndex,
          seriesType: series.type,
        };
        indoorMap.echarts.trigger("click", params);
      },
    });
    indoorMap.render();
    window._owIndoorMap = indoorMap;
  }

  async function navigateToFloor(newIndex) {
    const floorplanState = getFloorplanState();
    if (!floorplanState?.state) return;
    floorplanState.selectedIndex = newIndex;
    const maxStart = Math.max(0, floorplanState.floors.length - NAV_WINDOW_SIZE);
    const center = Math.floor(NAV_WINDOW_SIZE / 2);
    floorplanState.navWindowStart = Math.max(
      0,
      Math.min(floorplanState.selectedIndex - center, maxStart),
    );
    addFloorButtons();
    floorplanState.state.currentFloor =
      floorplanState.floors[floorplanState.selectedIndex];
    setFloorplanState(floorplanState);
    $(".floorplan-loading-spinner").show();
    await showFloor(floorplanState.state.url, floorplanState.state.currentFloor);
  }

  // Delegated event handlers (set up once at module init)
  $(document).on("click", "#floorplan-close-btn", destroyFloorplan);

  $(document).on("keydown", function (e) {
    if (e.key === "Escape" && document.getElementById("floorplan-overlay")) {
      destroyFloorplan();
    }
  });

  $(document).on("click", "#floorplan-navigation .floor-btn", async function (e) {
    if (!getFloorplanState()?.state) return;
    navigateToFloor(+e.currentTarget.dataset.index);
  });

  $(document).on(
    "click",
    "#floorplan-navigation .right-arrow:not(.disabled)",
    async function () {
      const floorplanState = getFloorplanState();
      if (
        !floorplanState?.state ||
        floorplanState.selectedIndex >= floorplanState.floors.length - 1
      )
        return;
      navigateToFloor(floorplanState.selectedIndex + 1);
    },
  );

  $(document).on(
    "click",
    "#floorplan-navigation .left-arrow:not(.disabled)",
    async function () {
      const floorplanState = getFloorplanState();
      if (!floorplanState?.state || floorplanState.selectedIndex <= 0) return;
      navigateToFloor(floorplanState.selectedIndex - 1);
    },
  );

  // React to URL fragment changes from the library (pushState, replaceState,
  // or browser back/forward navigation). Persistent at module level —
  // not tied to the overlay lifecycle.
  window.addEventListener("fragmentchange", () => {
    const indoorMapId = getIndoorMapIdFromUrl();
    const isOverlayOpen = document.getElementById("floorplan-overlay") !== null;
    if (indoorMapId) {
      if (!isOverlayOpen) {
        const { fragmentLocationId, fragmentFloor } = indoorMapId;
        const floorplanUrl = window._owGeoMapConfig.indoorCoordinatesUrl.replace(
          "000",
          fragmentLocationId,
        );
        openFloorPlan(floorplanUrl, fragmentLocationId, fragmentFloor);
      }
    } else if (isOverlayOpen) {
      destroyFloorplan();
    }
  });

  window.openFloorPlan = openFloorPlan;
})(django.jQuery);
