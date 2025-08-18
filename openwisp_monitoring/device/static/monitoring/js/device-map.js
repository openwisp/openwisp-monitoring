"use strict";

/*jshint esversion: 8 */
(function ($) {
  const loadingOverlay = $("#device-map-container .ow-loading-spinner");
  const localStorageKey = "ow-map-shown";
  const mapContainer = $("#device-map-container");
  const statuses = ["critical", "problem", "ok", "unknown", "deactivated"];
  window._owGeoMapConfig.STATUS_COLORS = {
    ok: "#267126",
    problem: "#ffb442",
    critical: "#a72d1d",
    unknown: "#353c44",
    deactivated: "#000",
  };
  const colors = window._owGeoMapConfig.STATUS_COLORS;
  const labels = window._owGeoMapConfig.labels;
  const getIndoorCoordinatesUrl = function (pk) {
    return window._owGeoMapConfig.indoorCoordinatesUrl.replace("000", pk);
  };
  const getLocationDeviceUrl = function (pk) {
    return window._owGeoMapConfig.locationDeviceUrl.replace("000", pk);
  };
  const getColor = function (data) {
    let deviceCount = data.device_count,
      findResult = function (func) {
        for (let i in statuses) {
          let status = statuses[i],
            statusCount = data[status + "_count"];
          if (statusCount === 0) {
            continue;
          }
          return func(status, statusCount);
        }
      };
    // if one status has absolute majority, it's the winner
    let majority = findResult(function (status, statusCount) {
      if (statusCount > deviceCount / 2) {
        return colors[status];
      }
    });
    if (majority) {
      return majority;
    }
    // otherwise simply return the color based on the priority
    return findResult(function (status, statusCount) {
      // if one status has absolute majority, it's the winner
      if (statusCount) {
        return colors[status];
      }
    });
  };

  let currentPopup = null;

  const loadPopUpContent = function (nodeData, netjsongraphInstance, url) {
    const map = netjsongraphInstance.leaflet;
    const locationId = nodeData?.properties?.id || nodeData.id;
    url = url || getLocationDeviceUrl(locationId);

    if (currentPopup) {
      currentPopup.remove();
    }
    loadingOverlay.show();

    $.ajax({
      dataType: "json",
      url: url,
      xhrFields: { withCredentials: true },
      success: function (apiData) {
        let html = "",
          device;
        for (let i = 0; i < apiData.results.length; i++) {
          device = apiData.results[i];
          html += `
            <tr>
                <td class="col-name"><a href="${device.admin_edit_url}">${device.name}</a></td>
                <td class="col-status">
                    <span class="health-status health-${device.monitoring.status}">
                        ${device.monitoring.status_label}
                    </span>
                </td>
            </tr>
          `;
        }

        const parts = [];
        if (apiData.previous) {
          parts.push(
            `<a class="prev" href="#prev" data-url="${apiData.previous}">‹ ${gettext("previous")}</a>`,
          );
        }
        if (apiData.next) {
          parts.push(
            `<a class="next" href="#next" data-url="${apiData.next}">${gettext("next")} ›</a>`,
          );
        }
        const pagination = parts.length
          ? `<p class="paginator">${parts.join(" ")}</p>`
          : "";

        const popupTitle = nodeData.label || nodeData?.properties?.name || nodeData.id;

        // Determine coordinates for the popup. We support:
        // 1. NetJSONGraph objects (nodeData.location)
        // 2. GeoJSON Point array (nodeData.coordinates)
        // 3. GeoJSON Feature geometry (nodeData.geometry.coordinates)
        // This fallback chain ensures the popup always plots at the correct
        // position regardless of datasource format.
        let latLng;
        if (nodeData.location && typeof nodeData.location.lat === "number") {
          latLng = [nodeData.location.lat, nodeData.location.lng];
        } else if (Array.isArray(nodeData.coordinates)) {
          latLng = [nodeData.coordinates[1], nodeData.coordinates[0]];
        } else if (nodeData.geometry?.coordinates?.length >= 2) {
          latLng = [nodeData.geometry.coordinates[1], nodeData.geometry.coordinates[0]];
        }

        if (!latLng || isNaN(latLng[0]) || isNaN(latLng[1])) {
          console.warn("Could not determine coordinates for popup", nodeData);
          loadingOverlay.hide();
          return;
        }

        const popupContent = `
          <div class="map-detail">
            <h2>${popupTitle} (${data.count})</h2>
            <div class="input-container">
              <input id="device-search" placeholder="Search for devices" />
            </div>
            <div class="label-container">
              ${statusFilterButtons}
              <input id="status-filter" type="hidden" />
            </div>
            <div class="table-container">
              <table>
                <thead>
                    <tr>
                        <th>${gettext("name")}</th>
                        <th class="th-status"><span class ="health-status-heading">${gettext(
                          "status",
                        )}</span></th>
                    </tr>
                </thead>
                <tbody></tbody>
                </table>
                <div class="ow-loading-spinner table-spinner"></div>
            </div>
            ${floorplan_btn}
          </div>
        `;

        currentPopup = L.popup().setLatLng(latLng).setContent(popupContent).openOn(map);

        const el = $(currentPopup.getElement());
        function renderRows() {
          if (devices.length === 0) {
            el.find("tbody").html(`
              <tr>
                <td class="no-devices" colspan="2">
                  ${gettext("No devices found!")}
                </td>
              </tr>
            `);
            return;
          }
          const rows = devices
            .map(
              (device) => `
            <tr>
                <td class="col-name"><a href="${device.admin_edit_url}">${device.name}</a></td>
                <td class="col-status">
                    <span class="health-status health-${device.monitoring.status}">
                        ${device.monitoring.status_label}
                    </span>
                </td>
            </tr>
          `,
            )
            .join("");
          el.find("tbody").html(rows);
        }
        let fetchDevicesTimeout;
        let loading = false;
        function fetchDevices(url, ms = 0) {
          if (!url || loading) return;
          clearTimeout(fetchDevicesTimeout);
          loading = true;
          const spinner = el.find(".table-spinner");
          const table = el.find(".table-container table");
          spinner.show();
          table.hide();
          fetchDevicesTimeout = setTimeout(() => {
            let params = new URLSearchParams();
            const searchParam = el
              .find("#device-search")
              .val()
              .toLowerCase()
              .trim();
            const statusParam = el.find("#status-filter").val();
            if (searchParam) {
              params.append("search", searchParam);
            }

            if (statusParam) {
              statusParam.split(",").forEach((status) => {
                params.append("status", status);
              });
            }
            const queryString = params.toString();
            let fetchUrl;
            // if nextUrl is the same as url, that means we are fetching for infinite scroll
            if (url === nextUrl) {
              fetchUrl = url;
            } else {
              fetchUrl = queryString ? `${url}?${queryString}` : url;
            }
            $.ajax({
              dataType: "json",
              url: fetchUrl,
              xhrFields: { withCredentials: true },
              success(data) {
                // If we are fetching for infinte scroll new need concat the results otherwise not
                if (url === nextUrl) {
                  devices = devices.concat(data.results);
                } else {
                  devices = data.results;
                }
                nextUrl = data.next;
                renderRows(devices);
              },
              error() {
                console.error("Could not load more devices from", url);
                alert("Could not load more devices.");
              },
              complete() {
                loading = false;
                spinner.hide();
                table.show();
              },
            });
          }, ms);
        }
        renderRows();
        el.find("#device-search").on("input", function () {
          fetchDevices(url, 300);
        });
        let activeStatuses = [];
        el.find(".status-filter").on("click", function (e) {
          e.stopPropagation();
          const btn = $(this);
          const status = btn.data("status");

          if (btn.hasClass("active")) {
            btn.removeClass("active");
            activeStatuses = activeStatuses.filter((s) => s !== status);
          } else {
            btn.addClass("active");
            activeStatuses.push(status);
          }
          $(`#status-filter`).val(activeStatuses.join(","));
          fetchDevices(url);
        });
        el.find(".table-container").on("scroll", function () {
          if (this.scrollTop + this.clientHeight >= this.scrollHeight - 10) {
            fetchDevices(nextUrl, 100);
          }
        });
        $(".floorplan-btn").on("click", function () {
          const floorplanUrl = getIndoorCoordinatesUrl(locationId);
          window.openFloorPlan(floorplanUrl);
        });
        loadingOverlay.hide();
      },
      error: function () {
        loadingOverlay.hide();
        alert(gettext("Error while retrieving data"));
      },
    });
  };

  const leafletConfig = JSON.parse($("#leaflet-config").text());
  const tiles = leafletConfig.TILES.map((tile) => {
    let tileLayer = tile[1];
    if (tileLayer.includes("https:")) {
      tileLayer = tileLayer.split("https:")[1];
    }
    let options = typeof tile[2] === "object" ? tile[2] : { attribution: tile[2] };
    return { label: tile[0], urlTemplate: `https:${tileLayer}`, options };
  });

  function onAjaxSuccess(data) {
    if (!data.count) {
      mapContainer.find(".no-data").fadeIn(500);
      loadingOverlay.hide();
      mapContainer.find(".no-data").click(function (e) {
        e.preventDefault();
        mapContainer.slideUp();
        localStorage.setItem(localStorageKey, "false");
      });
      return;
    } else {
      localStorage.removeItem(localStorageKey);
      mapContainer.slideDown();
  }

    if (Array.isArray(data.features)) {
      data.features.forEach((f) => {
        if (f?.id && f.properties && !f.properties.id) {
          f.properties.id = f.id;
        }
      });
    }

    const map = new NetJSONGraph(data, {
      el: "#device-map-container",
      render: "map",
      clustering: true,
      clusteringAttribute: "status",
      clusteringThreshold: 0,
      clusterRadius: 100,
      clusterSeparation: 20,
      disableClusteringAtLevel: 15,
      mapOptions: {
        // Use sensible fallback if the backend does not provide DEFAULT_CENTER.
        center: leafletConfig.DEFAULT_CENTER || [55.78, 11.54],
        zoom: leafletConfig.DEFAULT_ZOOM || 1,
        minZoom: leafletConfig.MIN_ZOOM || 1,
        maxZoom: leafletConfig.MAX_ZOOM || 18,
        fullscreenControl: true,

        // Force tooltips ON for all viewport widths; override library's
        // responsive media rules that hide tooltips under 851px.
        baseOptions: {
          media: [
            {
              query: { minWidth: 0 },
              option: { tooltip: { show: false } },
            },
          ],
        },
      },
      mapTileConfig: tiles,
      nodeCategories: Object.keys(colors).map((status) => ({
        name: status,
        nodeStyle: { color: colors[status] },
      })),
      // Hide ECharts node labels completely at any zoom level
      showLabelsAtZoomLevel: 0,
      echartsOption: {
        tooltip: {
          show: false, // Completely disable tooltips
        },
      },
      prepareData: function (json) {
        const items = json.nodes || json.features;
        if (Array.isArray(items)) {
          items.forEach((el) => {
            const props = el.properties || {};
            let status = props.status?.toLowerCase();
            if (!status) {
              const color = getColor(props);
              status =
                Object.keys(colors).find((k) => colors[k] === color) || "unknown";
            }
            props.status = status;
            props.category = status;
            el.category = status;
            if (!el.properties) el.properties = props;
          });
        }
        return json;
      },
      geoOptions: {
        style: function (feature) {
          return {
            radius: 9,
            fillColor: getColor(feature.properties),
            color: "rgba(0, 0, 0, 0.3)",
            weight: 3,
            opacity: 1,
            fillOpacity: 0.7,
          };
        },
        onEachFeature: function (feature, layer) {
          const color = getColor(feature.properties);
          feature.properties.status = Object.keys(colors).find(
            (key) => colors[key] === color,
          );

          layer.on("mouseover", function () {
            if (layer._tooltipDisabled) return;
            layer.unbindTooltip();
            if (!layer.isPopupOpen()) {
              layer.bindTooltip(feature.properties.name).openTooltip();
            }
          });

          layer.on("click", function () {
            const clickedLayer = this;
            // Close any open Leaflet tooltip before showing the popup
            clickedLayer.closeTooltip();
            clickedLayer.unbindTooltip();
            clickedLayer.unbindPopup();
            clickedLayer._tooltipDisabled = true; // block future hovers for this marker

            loadPopUpContent(feature, map);

            // Re-enable tooltip when the popup is closed
            map.leaflet.once("popupclose", function () {
              clickedLayer._tooltipDisabled = false;
            });
          });
        },
      },
      onClickElement: function (type, data) {
        if (type === "node") {
          loadPopUpContent(data, this);
        } else if (type === "Feature") {
          console.log("Clicked GeoJSON Feature:", data);
        }
      },
      onReady: function () {
        const map = this;
        let scale = { imperial: false, metric: false };
        if (leafletConfig.SCALE === "metric") {
          scale.metric = true;
        } else if (leafletConfig.SCALE === "imperial") {
          scale.imperial = true;
        } else if (leafletConfig.SCALE === "both") {
          scale.metric = true;
          scale.imperial = true;
        }
        if (leafletConfig.SCALE) {
          map.leaflet.addControl(new L.control.scale(scale));
        }

        try {
          const initialZoom = map.leaflet.getZoom();
          const showLabel = initialZoom >= map.config.showLabelsAtZoomLevel;
          map.echarts.setOption({
            series: [
              {
                label: { show: false },
                emphasis: { label: { show: showLabel } },
              },
            ],
          });
        } catch (e) {
          console.warn("Unable to set initial label visibility", e);
        }

        try {
          const features = (map.data && map.data.features) || [];
          if (features.length) {
            // Create a temporary layer just to calculate bounds – do NOT add it to the map
            const tempLayer = L.geoJSON(features);
            const bounds = tempLayer.getBounds();

            if (features.length === 1) {
              map.leaflet.setView(bounds.getCenter(), 10);
            } else {
              map.leaflet.fitBounds(bounds);
            }

            // Make sure points sit above polygons for interaction clarity
            tempLayer.eachLayer((layer) => {
              layer[
                layer.feature.geometry.type === "Point" ? "bringToFront" : "bringToBack"
              ]();
            });
          }
        } catch (err) {
          console.error("Unable to fit NetJSON bounds:", err);
        }

        // Restrict horizontal panning to three wrapped worlds
        map.leaflet.setMaxBounds(
          L.latLngBounds(L.latLng(-90, -540), L.latLng(90, 540)),
        );

        map.leaflet.on("moveend", (event) => {
          const netjsonGraph = map; // alias for clarity
          const bounds = event.target.getBounds();

          // Ensure data.features exists; otherwise skip wrap logic
          if (!netjsonGraph.data || !Array.isArray(netjsonGraph.data.features)) {
            return; // nothing to wrap
          }

          // When panning west past the dateline, clone features shifted −360°
          if (bounds._southWest.lng < -180 && !netjsonGraph.westWorldFeaturesAppended) {
            const westWorld = structuredClone(netjsonGraph.data);
            westWorld.features = westWorld.features.filter(
              (f) => !f.geometry || f.geometry.coordinates[0] <= 180,
            );
            westWorld.features.forEach((f) => {
              if (f.geometry) {
                f.geometry.coordinates[0] -= 360;
              }
            });
            netjsonGraph.utils.appendData(westWorld, netjsonGraph);
            netjsonGraph.westWorldFeaturesAppended = true;
          }

          // When panning east past the dateline, clone features shifted +360°
          if (bounds._northEast.lng > 180 && !netjsonGraph.eastWorldFeaturesAppended) {
            const eastWorld = structuredClone(netjsonGraph.data);
            eastWorld.features = eastWorld.features.filter(
              (f) => !f.geometry || f.geometry.coordinates[0] >= -180,
            );
            eastWorld.features.forEach((f) => {
              if (f.geometry) {
                f.geometry.coordinates[0] += 360;
              }
            });
            netjsonGraph.utils.appendData(eastWorld, netjsonGraph);
            netjsonGraph.eastWorldFeaturesAppended = true;
          }
        });
      },
    });

    map.setUtils({
      showLoading: function () {
        loadingOverlay.show();
      },
      hideLoading: function () {
        loadingOverlay.hide();
      },
      paginatedDataParse: async function (JSONParam) {
        let res;
        let data;
        try {
          res = await this.utils.JSONParamParse(JSONParam);
          data = res;
          while (res.next && data.features.length <= this.config.maxPointsFetched) {
            res = await this.utils.JSONParamParse(res.next);
            res = await res.json();
            data.features = data.features.concat(res.features);
          }
        } catch (e) {
          console.error(e);
        }
        return data;
      },
      // Added to open popup for a specific location Id in selenium tests
      openPopup: function (locationId) {
        const nodeData = map?.data?.nodes?.find((n) => n.id === locationId);
        loadPopUpContent(nodeData, map);
      },
    });
    map.render();
    window._owGeoMap = map;
  }

  if (localStorage.getItem(localStorageKey) === "false") {
    mapContainer.slideUp(50);
  }
  $.ajax({
    dataType: "json",
    url: window._owGeoMapConfig.geoJsonUrl,
    xhrFields: {
      withCredentials: true,
    },
    success: onAjaxSuccess,
    context: window,
  });
})(django.jQuery);