"use strict";

/* jshint esversion: 8 */
(function ($) {
  const loadingOverlay = $("#device-map-container .ow-loading-spinner");
  const localStorageKey = "ow-map-shown";
  const mapContainer = $("#device-map-container");
  const statuses = ["critical", "problem", "ok", "unknown", "deactivated"];
  const colors = {
    ok: "#267126",
    problem: "#ffb442",
    critical: "#a72d1d",
    unknown: "#353c44",
    deactivated: "#000000", // Fixed from "#0000"
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
    let majority = findResult(function (status, statusCount) {
      if (statusCount > deviceCount / 2) {
        return colors[status];
      }
    });
    if (majority) {
      return majority;
    }
    return findResult((status, statusCount) => {
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
              <td><a href="${device.admin_edit_url}">${device.name}</a></td>
              <td>
                <span class="health-status health-${device.monitoring.status}">${device.monitoring.status_label}</span>
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
            <h2>${popupTitle} (${apiData.count})</h2>
            <table>
              <thead>
                <tr><th>${gettext("name")}</th><th>${gettext("status")}</th></tr>
              </thead>
              <tbody>${html}</tbody>
            </table>
            ${pagination}
          </div>
        `;

        currentPopup = L.popup().setLatLng(latLng).setContent(popupContent).openOn(map);

        const $el = $(currentPopup.getElement());
        $el.find(".next").click(function (e) {
          e.preventDefault();
          loadPopUpContent(nodeData, netjsongraphInstance, $(this).data("url"));
        });
        $el.find(".prev").click(function (e) {
          e.preventDefault();
          loadPopUpContent(nodeData, netjsongraphInstance, $(this).data("url"));
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
        let res, data;
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
    });

    map.render();
  }

  if (localStorage.getItem(localStorageKey) === "false") {
    mapContainer.slideUp(50);
  }

  $.ajax({
    dataType: "json",
    url: window._owGeoMapConfig.geoJsonUrl,
    xhrFields: { withCredentials: true },
    success: onAjaxSuccess,
    context: window,
  });
})(django.jQuery);
